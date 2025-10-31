from celery import Celery
from celery.schedules import crontab
from app.core.config import settings

# Create Celery app
celery_app = Celery(
    "arbeit",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=['app.tasks']
)

# Celery configuration
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,  # 5 minutes
    task_soft_time_limit=240,  # 4 minutes
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=100,
)

# Celery Beat schedule (dynamic scheduling will be added later)
celery_app.conf.beat_schedule = {
    'health-check': {
        'task': 'app.tasks.health_check_task',
        'schedule': crontab(minute='*/30'),  # Every 30 minutes
    },
    'run-all-scrapers': {
        'task': 'app.tasks.run_all_scrapers',
        'schedule': crontab(minute='*/60'),  # Every hour
    },
    'scrape-high-priority': {
        'task': 'app.tasks.run_scraper',
        'schedule': crontab(minute='*/30'),  # Every 30 minutes
        'args': ('RemoteOK',),  # High priority source
    },
}

if __name__ == '__main__':
    celery_app.start()