web: daphne -b 0.0.0.0 -p $PORT Handcrafts.asgi:application
worker: celery -A Handcrafts worker -l info
beat: celery -A Handcrafts beat -l info