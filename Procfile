release: python manage.py migrate --noinput
web: python manage.py collectstatic --noinput && gunicorn srdc.wsgi:application --bind 0.0.0.0:$PORT
