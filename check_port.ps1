Get-NetTCPConnection -State Listen | Where-Object { $_.LocalPort -eq 8000 } | ForEach-Object { Write-Output "Port: $($_.LocalPort) PID: $($_.OwningProcess)" }
Get-Process -Name python -ErrorAction SilentlyContinue | ForEach-Object { Write-Output "Python PID: $($_.Id) StartTime: $($_.StartTime)" }
