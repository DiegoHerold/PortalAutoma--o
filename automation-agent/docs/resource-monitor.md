# Resource Monitor

Responde à pergunta: **Como a máquina está neste momento?**

## Métricas coletadas

```mermaid
flowchart TD
    Timer["Timer\n(intervalo configurável)"] --> Collect
    Collect --> CPU["CPU %"]
    Collect --> MEM["Memória total/disponível/usada"]
    Collect --> DISK["Disco total/livre"]
    Collect --> AGENT["Memória do Agent"]
    Collect --> PROC["Contagem de processos"]
    Collect --> UP["Uptime"]
    Collect --> DB["Tamanho do banco"]
    Collect --> LOG["Tamanho dos logs"]
    Collect --> SPOOL["Tamanho do spool"]
    Collect --> CACHE["Tamanho do cache"]
    Collect --> SESSION["Estado da sessão"]
    CPU & MEM & DISK --> SQLite["SQLite\nresource_samples"]
    SQLite --> Metrics["Métricas agregadas\n(média, máximo)"]
```

## Configuração

```json
{
  "Monitoring": {
    "SampleIntervalSeconds": 5,
    "HistoryRetentionMinutes": 60
  }
}
```
