# Starts the local PostgreSQL 16 server used by the demo (no admin rights / Windows service needed).
$pg = "C:\Users\Ragunathan\PostgreSQL16"
& "$pg\bin\pg_ctl.exe" -D "$pg\data" -l "$pg\server.log" -o "-p 5432" status *> $null
if ($LASTEXITCODE -eq 0) { Write-Host "PostgreSQL is already running." -ForegroundColor Green; exit 0 }
& "$pg\bin\pg_ctl.exe" -D "$pg\data" -l "$pg\server.log" -o "-p 5432" -w start
if ($LASTEXITCODE -eq 0) { Write-Host "PostgreSQL started on port 5432." -ForegroundColor Green }
else { Write-Host "PostgreSQL failed to start - see $pg\server.log" -ForegroundColor Red }
