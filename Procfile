web: gunicorn --worker-tmp-dir /dev/shm --worker-class=gthread --threads 4 --workers 2 --timeout 1200 --bind 0.0.0
.0:$PORT app:app
