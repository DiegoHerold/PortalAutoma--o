# Machine Profiler

Responde à pergunta: **Quais são as características desta máquina?**

## Coleta

```mermaid
flowchart LR
    OS["OS Info\n(nome, build, arch)"] --> Profile
    CPU["CPU Info\n(modelo, cores)"] --> Profile
    RAM["Memory Info\n(total, disponível)"] --> Profile
    Disk["Disk Info\n(volume, espaço)"] --> Profile
    Session["Session Info\n(usuário, tipo, resolução)"] --> Profile
    Software["Software\n(Chrome, Edge, Domínio...)"] --> Profile
    Caps["Capabilities\n(windows, browser, desktop)"] --> Profile
    Profile["MachineProfileSnapshot"]
```

## Software detectado

- Google Chrome
- Microsoft Edge
- Microsoft Excel / Office
- WebView2
- PowerShell
- Domínio Contábil

Detecção usa registro do Windows e caminhos conhecidos.
Nunca assume instalação apenas por existir uma pasta.
