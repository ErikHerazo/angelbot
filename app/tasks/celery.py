from celery import Celery
from app.core.config import Settings


app = Celery('angelbot',
             broker=Settings.CELERY_BROKER_URL,
             backend=Settings.CELERY_RESULT_BACKEND,
             include=['app.tasks.tasks'])

# Optional configuration, see the application user guide.
app.conf.update(
    result_expires=3600,
)

if __name__ == '__main__':
    app.start()
