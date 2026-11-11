/*
 * Notificações (Fase 6): os avisos de cada pessoa e o que ela escolhe receber.
 * O e-mail sai pelo Microsoft Graph só quando o envio estiver ligado no portal; até lá
 * os avisos ficam no sino.
 */

export type Aviso = {
  id: string;
  tipos: string[];
  titulo: string;
  texto: string;
  link: string | null;
  quando: string;
  lida: boolean;
  email: "pendente" | "enviado" | "expirado" | "falhou";
};

export type Avisos = { avisos: Aviso[]; nao_lidas: number };

export type EnvioPorEmail = "desligado" | "incompleto" | "ligado";

export type PreferenciaDeAvisos = {
  tipos: string[];
  fila_minutos: number;
  email: string | null;
  disponiveis: Array<{ tipo: string; rotulo: string; so_gestores: boolean }>;
  fila_minutos_limites: [number, number];
  envio_por_email: EnvioPorEmail;
};

export const DESCRICOES: Record<string, string> = {
  erro: "Quando uma execução que você pode ver termina com erro.",
  atencao: "Quando um item para e precisa de uma pessoa.",
  maquina_offline: "Quando uma máquina para de dar sinal.",
  fila_parada: "Quando há jobs esperando e nenhum começa há mais do que o tempo escolhido.",
  termino: "Quando uma execução que você pode ver termina (com ou sem erro).",
};

export const ENVIO: Record<EnvioPorEmail, string> = {
  desligado: "O envio por e-mail ainda não está ligado no portal. Os avisos aparecem no sino, no topo da tela.",
  incompleto: "O envio por e-mail foi ligado, mas falta configurar o Microsoft Graph. Os avisos aparecem no sino.",
  ligado: "Os avisos também chegam por e-mail (um por evento, no máximo).",
};
