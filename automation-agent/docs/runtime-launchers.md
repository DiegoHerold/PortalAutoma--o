# Runtime Launchers

Cada tipo de entrypoint possui um launcher especializado que constrói o `LaunchSpec` para o ExecutionHost.

## Python Function Launcher

Executa uma função Python importada do pacote:

```python
import modulo; modulo.funcao()
```

- Define `PYTHONPATH` para o diretório do pacote
- Recebe input via `AUTOMATION_INPUT_PATH`
- Gera output em `AUTOMATION_OUTPUT_PATH`

## Python Module Launcher

Executa um módulo Python com `-m`:

```
python -m modulo
```

Útil para automações que usam `__main__.py`.

## PowerShell Launcher

Executa script PowerShell com flags de segurança:

```
pwsh.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File script.ps1
```

## Executable Launcher

Executa executável validado dentro do pacote ou runtime. Valida que o executável está dentro dos diretórios permitidos.

## Browser Playwright Launcher

Similar ao Python Function, mas com variáveis adicionais:

- `PLAYWRIGHT_BROWSERS_PATH` → Browsers do runtime
- `PLAYWRIGHT_BROWSER_DATA` → Profile isolado por execução

Cada execução browser possui:
- Browser profile próprio
- User data directory próprio
- Downloads próprios
- Sem compartilhamento de sessão ou cookies
