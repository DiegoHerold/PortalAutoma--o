/** "agora", "há 12 min", "há 3 h", "ontem", "há 5 dias" ou a data. */
export function haQuanto(iso: string | null | undefined, agora: Date = new Date()): string {
  if (!iso) return "—";
  const minutos = Math.round((agora.getTime() - new Date(iso).getTime()) / 60000);
  if (minutos < 1) return "agora";
  if (minutos < 60) return `há ${minutos} min`;
  const horas = Math.floor(minutos / 60);
  if (horas < 24) return `há ${horas} h`;
  const dias = Math.floor(horas / 24);
  if (dias === 1) return "ontem";
  if (dias < 60) return `há ${dias} dias`;
  return new Date(iso).toLocaleDateString("pt-BR");
}
