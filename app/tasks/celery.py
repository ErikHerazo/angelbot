from celery import Celery
from app.core.config import Settings


app = Celery('angelbot',
             broker=Settings.CELERY_BROKER_URL,
             backend=Settings.CELERY_RESULT_BACKEND,
             include=['app.tasks.tasks'])

# Optional configuration, see the application user guide.
app.conf.update(
    result_expires=3600,

    broker_connection_retry_on_startup=True,
    broker_connection_max_retries=None,

    redis_socket_keepalive=True,
    redis_retry_on_timeout=True,

    broker_pool_limit=None,
)

# SSL for Azure Redis
app.conf.broker_use_ssl = {
    "ssl_cert_reqs": None
}

app.conf.redis_backend_use_ssl = {
    "ssl_cert_reqs": None
}

if __name__ == '__main__':
    app.start()
