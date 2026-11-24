# Stops the local PostgreSQL 16 server.
$pg = "C:\Users\Ragunathan\PostgreSQL16"
& "$pg\bin\pg_ctl.exe" -D "$pg\data" -m fast stop
