# SRDC Admin

Django app for local/LAN boutique customer, measurement, order, billing, and print workflows.

## Local setup

```powershell
python -m venv venv
venv\Scripts\python.exe -m pip install -r requirements.txt
```

Create a PostgreSQL database named `srdc`, then set environment variables if your local values differ:

```powershell
$env:DJANGO_SECRET_KEY="change-this"
$env:DJANGO_DEBUG="true"
$env:DJANGO_ALLOWED_HOSTS="localhost,127.0.0.1,0.0.0.0,192.168.1.10"
$env:DB_NAME="srdc"
$env:DB_USER="postgres"
$env:DB_PASSWORD="pg@123"
$env:DB_HOST="localhost"
$env:DB_PORT="5432"
```

Run the app:

```powershell
venv\Scripts\python.exe manage.py migrate
venv\Scripts\python.exe manage.py createsuperuser
venv\Scripts\python.exe manage.py runserver 0.0.0.0:8000
```

Open `http://localhost:8000/` on the store machine. Other devices on the same LAN can use `http://<store-machine-ip>:8000/` when that IP is listed in `DJANGO_ALLOWED_HOSTS`.

## Backup and restore

```powershell
pg_dump -h localhost -U postgres -Fc srdc > srdc-backup.dump
createdb -h localhost -U postgres srdc_restored
pg_restore -h localhost -U postgres -d srdc_restored srdc-backup.dump
```

## Checks

```powershell
venv\Scripts\python.exe manage.py check
venv\Scripts\python.exe manage.py test
```
