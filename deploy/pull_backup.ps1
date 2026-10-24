# Run on your Windows PC (Task Scheduler, daily): copies the server's newest backups to your own computer.
# Usage: .\pull_backup.ps1 -Server user@host -RemoteDir /opt/timelog/backups
param(
  [Parameter(Mandatory)] [string]$Server,
  [string]$RemoteDir = "/opt/timelog/backups",
  [string]$LocalDir = "D:\My Drive\TimeLogBackups\web"
)
New-Item -ItemType Directory -Force $LocalDir | Out-Null
scp -r "${Server}:${RemoteDir}/daily" "${Server}:${RemoteDir}/weekly" $LocalDir
if ($LASTEXITCODE -ne 0) { Write-Error "backup pull failed"; exit 1 }
Write-Host "backups copied to $LocalDir"
