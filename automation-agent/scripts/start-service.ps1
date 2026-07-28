param([string]$ServiceName = "BiasonAutomationAgent")
sc.exe start $ServiceName
