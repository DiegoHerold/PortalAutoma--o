param([string]$ServiceName = "BiasonAutomationAgent")
sc.exe stop $ServiceName
