# Ciclo de Vida do Agent

Status: vigente.

## Registro

```mermaid
sequenceDiagram
    participant A as Agent
    participant P as Portal
    A->>P: register(machine_id, hostname, version, capabilities)
    P->>P: cria ou reconcilia Agent
    P-->>A: agent_id, device_token, policy, protocol_version
    A->>A: persiste identidade local
```

## Conexao

```mermaid
sequenceDiagram
    participant A as Agent
    participant P as Portal
    A->>P: WebSocket hello(agent_id, agent_instance_id)
    P->>P: valida token, instancia e protocolo
    P-->>A: accepted(config, command_sequence)
    A-->>P: heartbeat + resource snapshot
```

Cada Agent mantem uma unica conexao WebSocket ativa com o Portal. Nao crie
WebSocket por automacao ou execucao.

## Heartbeat

```mermaid
sequenceDiagram
    participant A as Agent
    participant P as Portal
    loop intervalo configurado
        A-->>P: heartbeat(connectivity, resources, pools, running_attempts)
        P->>P: persiste snapshot recente e calcula presenca
        P-->>A: heartbeat.ack(server_time, desired_config_revision)
    end
```

Heartbeat nao sobrescreve politica administrativa. Snapshots possuem
`observed_at`, `agent_instance_id`, `revision` e `ttl`.

## Estados por dimensao

Conectividade:

- `connecting`
- `online`
- `stale`
- `disconnected`
- `offline`

Administrativo:

- `pending_registration`
- `enabled`
- `draining`
- `maintenance`
- `updating`
- `disabled`

Saude:

- `healthy`
- `degraded`
- `error`

Ocupacao calculada:

- `idle`
- `busy`
- `saturated`

## Responsabilidades do Agent

- Identidade local e `AgentInstance`.
- Descoberta de capabilities.
- Analise de CPU, memoria, disco, sessao e softwares.
- Calculo de capacidade recomendada.
- Aplicacao da politica recebida.
- Validacao final da oferta.
- Reserva local, preparacao de runtime/pacote, isolamento e execucao.
- Monitoramento, cancelamento e encerramento da arvore de processos.
- Eventos estruturados, spool offline, upload de artefatos e recuperacao local.

O Agent nao escolhe automacoes por conta propria, nao cria execucoes oficiais,
nao publica pacotes, nao controla fluxos, nao mantem estado global e nao inicia
uma oferta apenas porque a aceitou.

