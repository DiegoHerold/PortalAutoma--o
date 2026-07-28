# Capabilities

Cada capability é tipada e versionada, alinhada com `contracts/capabilities/capability.schema.json`.

## Capabilities iniciais

| Key | Descrição |
|-----|-----------|
| windows | Sistema operacional Windows |
| windows.x64 | Arquitetura 64-bit |
| powershell | PowerShell disponível |
| browser.chrome | Google Chrome instalado |
| browser.edge | Microsoft Edge instalado |
| browser.webview2 | WebView2 runtime |
| office.excel | Microsoft Excel |
| dominio.installed | Domínio Contábil |
| desktop_automation | Automação de desktop (futuro) |
| interactive_session | Sessão interativa ativa |
| rdp_session / local_session | Tipo de sessão |
| agent.background_execution | Execução em background (futuro) |
| agent.browser_execution | Execução em browser (futuro) |
| agent.interactive_execution | Execução interativa (futuro) |

## Status

`available`, `unavailable`, `unknown`, `not_configured`, `degraded`
