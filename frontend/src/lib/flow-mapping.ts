// Espelho em TypeScript de backend/modules/orchestration/flows/domain/mapping.py.
// Usado só para a prévia/"testar mapping" no editor — o backend continua sendo a
// única fonte de verdade na hora de executar o Fluxo de verdade.

export type MappingSpec = { value: unknown } | { source: string; path?: string } | unknown;

export class MappingError extends Error {
  code: string;
  details: Record<string, unknown>;
  constructor(code: string, message: string, details: Record<string, unknown> = {}) {
    super(message);
    this.code = code;
    this.details = details;
  }
}

export type MappingContext = {
  flow: { input: Record<string, unknown>; metadata?: Record<string, unknown> };
  nodes: Record<string, { status?: string; output?: unknown; input?: unknown }>;
};

export function resolveMapping(mapping: Record<string, MappingSpec> | null | undefined, context: MappingContext): Record<string, unknown> {
  if (!mapping || Object.keys(mapping).length === 0) return { ...(context.flow?.input ?? {}) };
  const resolved: Record<string, unknown> = {};
  for (const [key, spec] of Object.entries(mapping)) {
    resolved[key] = resolveValue(spec, context);
  }
  return resolved;
}

export function resolveValue(spec: MappingSpec, context: MappingContext): unknown {
  if (typeof spec !== "object" || spec === null) return spec;
  const record = spec as Record<string, unknown>;
  let raw: unknown;
  if ("value" in record) {
    raw = record.value;
  } else {
    const source = String(record.source ?? "");
    const path = String(record.path ?? "$");
    const sourceValue = sourceValueOf(source, context);
    raw = pathOf(sourceValue, path);
  }
  return applyTransforms(raw, record.transform);
}

// Espelha backend/modules/orchestration/flows/domain/mapping.py::TRANSFORMS — usado pelo
// bloco "Transform Data" (e disponível a qualquer mapping) no editor.
export const TRANSFORMS: Record<string, (value: unknown) => unknown> = {
  uppercase: (value) => (typeof value === "string" ? value.toUpperCase() : value),
  lowercase: (value) => (typeof value === "string" ? value.toLowerCase() : value),
  trim: (value) => (typeof value === "string" ? value.trim() : value),
  capitalize: (value) => (typeof value === "string" && value.length > 0 ? value[0].toUpperCase() + value.slice(1).toLowerCase() : value),
  to_string: (value) => (value === null || value === undefined ? value : typeof value === "string" ? value : JSON.stringify(value)),
  to_number: (value) => {
    if (value === null || value === undefined || value === "") return null;
    const asNumber = Number(value);
    if (Number.isNaN(asNumber)) throw new MappingError("TRANSFORM_VALUE_INVALID", "Valor não pode ser convertido em número.", { value });
    return asNumber;
  },
  round: (value) => {
    if (value === null || value === undefined || value === "") return null;
    const asNumber = Number(value);
    if (Number.isNaN(asNumber)) throw new MappingError("TRANSFORM_VALUE_INVALID", "Valor não pode ser arredondado.", { value });
    return Math.round(asNumber);
  },
};

export const TRANSFORM_OPTIONS = [
  { value: "uppercase", label: "Maiúsculas" },
  { value: "lowercase", label: "minúsculas" },
  { value: "trim", label: "Remover espaços nas pontas" },
  { value: "capitalize", label: "Capitalizar" },
  { value: "to_string", label: "Converter em texto" },
  { value: "to_number", label: "Converter em número" },
  { value: "round", label: "Arredondar" },
] as const;

function applyTransforms(value: unknown, transform: unknown): unknown {
  if (!transform) return value;
  const steps = Array.isArray(transform) ? transform : [transform];
  let current = value;
  for (const step of steps) {
    const fn = TRANSFORMS[String(step)];
    if (!fn) throw new MappingError("TRANSFORM_INVALID", `Transformação desconhecida: "${step}".`, { transform: step });
    current = fn(current);
  }
  return current;
}

function sourceValueOf(source: string, context: MappingContext): unknown {
  if (source === "flow.input") return context.flow?.input;
  if (source === "flow.metadata") return context.flow?.metadata;
  if (source.startsWith("node.") && source.endsWith(".output")) {
    const key = source.slice("node.".length, source.length - ".output".length);
    return context.nodes?.[key]?.output;
  }
  if (source.startsWith("node.") && source.endsWith(".status")) {
    const key = source.slice("node.".length, source.length - ".status".length);
    return context.nodes?.[key]?.status;
  }
  throw new MappingError("MAPPING_SOURCE_INVALID", `Fonte de mapping inválida: "${source}".`, { source });
}

function pathOf(value: unknown, path: string): unknown {
  if (path === "" || path === "$") return value;
  if (!path.startsWith("$.")) {
    throw new MappingError("MAPPING_PATH_INVALID", 'Path deve usar sintaxe "$.campo.subcampo".', { path });
  }
  let current: unknown = value;
  for (const part of path.slice(2).split(".")) {
    if (!part || part.startsWith("_")) {
      throw new MappingError("MAPPING_PATH_INVALID", "Path contém segmento inválido.", { path });
    }
    if (current && typeof current === "object" && !Array.isArray(current)) {
      current = (current as Record<string, unknown>)[part];
    } else {
      return null;
    }
  }
  return current;
}

export const MAPPING_SOURCE_OPTIONS = [
  { value: "flow.input", label: "Entrada do fluxo" },
  { value: "flow.metadata", label: "Metadados do fluxo" },
  { value: "node.output", label: "Saída de outro nó" },
  { value: "node.status", label: "Status de outro nó" },
  { value: "constant", label: "Valor constante" },
] as const;

export function sourceKindOf(spec: MappingSpec): string {
  if (typeof spec !== "object" || spec === null) return "constant";
  const record = spec as Record<string, unknown>;
  if ("value" in record) return "constant";
  const source = String(record.source ?? "");
  if (source === "flow.input" || source === "flow.metadata") return source;
  if (source.endsWith(".output")) return "node.output";
  if (source.endsWith(".status")) return "node.status";
  return "flow.input";
}

export function nodeKeyOf(spec: MappingSpec): string {
  if (typeof spec !== "object" || spec === null) return "";
  const source = String((spec as Record<string, unknown>).source ?? "");
  const match = /^node\.(.+)\.(output|status)$/.exec(source);
  return match ? match[1] : "";
}
