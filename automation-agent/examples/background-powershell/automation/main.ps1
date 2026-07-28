# Background PowerShell Example Automation
# Reads parameters, generates output file, writes stdout

$ErrorActionPreference = "Stop"

$workspace = $env:AUTOMATION_WORKSPACE
$inputPath = Join-Path $env:AUTOMATION_INPUT_PATH "input.json"
$outputPath = $env:AUTOMATION_OUTPUT_PATH
$artifactsPath = $env:AUTOMATION_ARTIFACTS_PATH

Write-Host "PowerShell automation starting..."
Write-Host "Workspace: $workspace"

# Read input parameters
$params = @{}
if (Test-Path $inputPath) {
    $params = Get-Content $inputPath -Raw | ConvertFrom-Json
    Write-Host "Loaded input parameters"
}

# Simulate processing
$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
Write-Host "Processing at $timestamp"

# Generate output
$result = @{
    status = "completed"
    timestamp = $timestamp
    hostname = $env:COMPUTERNAME
    message = "PowerShell automation executed successfully"
}

$resultJson = $result | ConvertTo-Json -Depth 3
$resultPath = Join-Path $outputPath "output.json"
$resultJson | Out-File -FilePath $resultPath -Encoding UTF8
Write-Host "Output written to $resultPath"

# Create artifact
$reportPath = Join-Path $artifactsPath "system_info.txt"
@"
System Information Report
========================
Hostname: $($env:COMPUTERNAME)
OS: $([System.Environment]::OSVersion.VersionString)
CLR Version: $([System.Environment]::Version)
Timestamp: $timestamp
"@ | Out-File -FilePath $reportPath -Encoding UTF8

Write-Host "Artifact written to $reportPath"
Write-Host "PowerShell automation completed successfully"

exit 0
