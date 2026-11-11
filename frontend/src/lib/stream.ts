import { API_BASE_URL } from "@/lib/constants";

/**
 * Leitor de SSE por `fetch`, com o token no cabeçalho `Authorization`.
 *
 * O `EventSource` do navegador só aceita credencial na URL, e a regra do portal é que
 * credencial nunca aparece em URL (fica em log de proxy, histórico e Referer). Aqui a
 * conexão reconecta sozinha com espera crescente e retoma de onde parou pelo
 * `Last-Event-ID`. Para em 401/403: sem permissão não adianta insistir.
 */

export type EventoSse = { evento: string; dados: string; id?: string };

type Opcoes = {
  aoMudarConexao?: (conectado: boolean) => void;
  /** Chamado uma vez quando o servidor recusa (401/403). */
  aoRecusar?: (status: number) => void;
};

export function abrirStream(
  caminho: string,
  token: string,
  aoReceber: (evento: EventoSse) => void,
  { aoMudarConexao, aoRecusar }: Opcoes = {},
): () => void {
  const controle = new AbortController();
  let ultimoId: string | undefined;
  let tentativa = 0;
  let parado = false;

  const esperar = (ms: number) =>
    new Promise<void>((resolve) => {
      const t = setTimeout(resolve, ms);
      controle.signal.addEventListener("abort", () => {
        clearTimeout(t);
        resolve();
      });
    });

  async function ciclo() {
    while (!parado) {
      try {
        const cabecalhos: Record<string, string> = { Authorization: `Bearer ${token}`, Accept: "text/event-stream" };
        if (ultimoId) cabecalhos["Last-Event-ID"] = ultimoId;
        const resposta = await fetch(`${API_BASE_URL}${caminho}`, {
          headers: cabecalhos,
          cache: "no-store",
          signal: controle.signal,
        });
        if (resposta.status === 401 || resposta.status === 403 || resposta.status === 404) {
          aoRecusar?.(resposta.status);
          aoMudarConexao?.(false);
          return;
        }
        if (!resposta.ok || !resposta.body) throw new Error(`stream ${resposta.status}`);
        tentativa = 0;
        aoMudarConexao?.(true);
        const leitor = resposta.body.getReader();
        const decodificador = new TextDecoder();
        let acumulado = "";
        for (;;) {
          const { value, done } = await leitor.read();
          if (done) break;
          acumulado += decodificador.decode(value, { stream: true }).replace(/\r\n/g, "\n");
          let fim = acumulado.indexOf("\n\n");
          while (fim >= 0) {
            const bloco = acumulado.slice(0, fim);
            acumulado = acumulado.slice(fim + 2);
            const evento = interpretar(bloco);
            if (evento) {
              if (evento.id) ultimoId = evento.id;
              aoReceber(evento);
            }
            fim = acumulado.indexOf("\n\n");
          }
        }
      } catch {
        if (parado) return;
      }
      aoMudarConexao?.(false);
      tentativa = Math.min(tentativa + 1, 5);
      await esperar(Math.min(1000 * 2 ** tentativa, 20000));
    }
  }

  void ciclo();
  return () => {
    parado = true;
    controle.abort();
  };
}

function interpretar(bloco: string): EventoSse | null {
  let evento = "message";
  let id: string | undefined;
  const dados: string[] = [];
  for (const linha of bloco.split("\n")) {
    if (!linha || linha.startsWith(":")) continue; // comentário = manter a conexão viva
    const separador = linha.indexOf(":");
    const campo = separador < 0 ? linha : linha.slice(0, separador);
    const valor = separador < 0 ? "" : linha.slice(separador + 1).replace(/^ /, "");
    if (campo === "event") evento = valor;
    else if (campo === "data") dados.push(valor);
    else if (campo === "id") id = valor;
  }
  if (dados.length === 0 && evento === "message") return null;
  return { evento, dados: dados.join("\n"), id };
}
