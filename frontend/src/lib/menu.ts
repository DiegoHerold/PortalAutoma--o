"use client";

import { useCallback, useEffect, useState } from "react";

import { ALL_NAV_ITEMS, NAV_GROUPS, type NavItem } from "@/lib/navigation";

/*
 * Quais itens aparecem no menu lateral. A pessoa escolhe nas Configurações; a escolha fica
 * neste navegador. Sem escolha, vale o padrão de cada item (``padrao`` em navigation.ts).
 */
const CHAVE = "portal.menu.itens";
const EVENTO = "portal-menu-mudou";

export function itensPadrao(): Set<string> {
  return new Set(ALL_NAV_ITEMS.filter((i) => i.padrao !== false).map((i) => i.href));
}

function ler(): Set<string> {
  try {
    const salvo = window.localStorage.getItem(CHAVE);
    if (salvo) return new Set(JSON.parse(salvo) as string[]);
  } catch {
    /* sem armazenamento ou valor quebrado: padrão */
  }
  return itensPadrao();
}

export function salvarMenu(itens: Set<string> | null): void {
  try {
    if (itens === null) window.localStorage.removeItem(CHAVE);
    else window.localStorage.setItem(CHAVE, JSON.stringify([...itens]));
  } catch {
    /* ignora */
  }
  window.dispatchEvent(new Event(EVENTO));
}

/** Itens escolhidos para o menu, atualizados na hora quando a pessoa muda nas Configurações. */
export function useMenuItens(): Set<string> {
  const [visiveis, setVisiveis] = useState<Set<string>>(() => itensPadrao());
  useEffect(() => {
    const atualizar = () => setVisiveis(ler());
    atualizar();
    window.addEventListener(EVENTO, atualizar);
    window.addEventListener("storage", atualizar);
    return () => {
      window.removeEventListener(EVENTO, atualizar);
      window.removeEventListener("storage", atualizar);
    };
  }, []);
  return visiveis;
}

export function useMenuVisivel(): (item: NavItem) => boolean {
  const visiveis = useMenuItens();
  return useCallback((item: NavItem) => visiveis.has(item.href), [visiveis]);
}

/*
 * Ordem do menu: a pessoa arrasta itens (dentro da categoria) e categorias no próprio menu
 * lateral. Fica neste navegador, como a escolha dos itens.
 */
const CHAVE_ORDEM = "portal.menu.ordem";

export type OrdemDoMenu = { grupos: string[]; itens: string[] };

function ordemPadrao(): OrdemDoMenu {
  return { grupos: NAV_GROUPS.map((g) => g.label), itens: NAV_GROUPS.flatMap((g) => g.items.map((i) => i.href)) };
}

function lerOrdem(): OrdemDoMenu {
  try {
    const salvo = window.localStorage.getItem(CHAVE_ORDEM);
    if (salvo) {
      const o = JSON.parse(salvo) as Partial<OrdemDoMenu>;
      if (Array.isArray(o.grupos) && Array.isArray(o.itens)) return { grupos: o.grupos.map(String), itens: o.itens.map(String) };
    }
  } catch {
    /* sem armazenamento ou valor quebrado: padrão */
  }
  return ordemPadrao();
}

export function salvarOrdem(ordem: OrdemDoMenu | null): void {
  try {
    if (ordem === null) window.localStorage.removeItem(CHAVE_ORDEM);
    else window.localStorage.setItem(CHAVE_ORDEM, JSON.stringify(ordem));
  } catch {
    /* ignora */
  }
  window.dispatchEvent(new Event(EVENTO));
}

/** Volta itens e ordem ao padrão. */
export function restaurarMenu(): void {
  salvarOrdem(null);
  salvarMenu(null);
}

/** Posição de cada nome na ordem salva; o que não está lá (item novo) vem depois, na ordem padrão. */
function posicoes(salvos: string[], padrao: string[]): Map<string, number> {
  const mapa = new Map<string, number>();
  salvos.forEach((v, i) => mapa.set(v, i));
  padrao.forEach((v, i) => !mapa.has(v) && mapa.set(v, salvos.length + i));
  return mapa;
}

/** Ordem completa (todas as categorias e itens), com o que é novo no fim. */
export function completar(ordem: OrdemDoMenu): OrdemDoMenu {
  const padrao = ordemPadrao();
  const pg = posicoes(ordem.grupos, padrao.grupos);
  const pi = posicoes(ordem.itens, padrao.itens);
  return {
    grupos: [...padrao.grupos].sort((a, b) => pg.get(a)! - pg.get(b)!),
    itens: [...padrao.itens].sort((a, b) => pi.get(a)! - pi.get(b)!),
  };
}

export function aplicarOrdem<G extends { label: string; items: NavItem[] }>(grupos: G[], ordem: OrdemDoMenu): G[] {
  const o = completar(ordem);
  const pg = new Map(o.grupos.map((g, i) => [g, i]));
  const pi = new Map(o.itens.map((h, i) => [h, i]));
  return [...grupos]
    .sort((a, b) => (pg.get(a.label) ?? 0) - (pg.get(b.label) ?? 0))
    .map((g) => ({ ...g, items: [...g.items].sort((a, b) => (pi.get(a.href) ?? 0) - (pi.get(b.href) ?? 0)) }));
}

/** Move ``de`` para o lugar de ``para`` (o resto anda uma casa). */
export function mover(lista: string[], de: string, para: string): string[] {
  const i = lista.indexOf(de);
  const j = lista.indexOf(para);
  if (i < 0 || j < 0 || i === j) return lista;
  const nova = [...lista];
  nova.splice(i, 1);
  nova.splice(j, 0, de);
  return nova;
}

export function useMenuOrdem(): OrdemDoMenu {
  const [ordem, setOrdem] = useState<OrdemDoMenu>(() => ordemPadrao());
  useEffect(() => {
    const atualizar = () => setOrdem(lerOrdem());
    atualizar();
    window.addEventListener(EVENTO, atualizar);
    window.addEventListener("storage", atualizar);
    return () => {
      window.removeEventListener(EVENTO, atualizar);
      window.removeEventListener("storage", atualizar);
    };
  }, []);
  return ordem;
}
