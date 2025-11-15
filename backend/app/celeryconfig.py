"""Celery configuration."""
from kombu import Exchange, Queue
from app.config import settings

# Broker settings
broker_url = settings.REDIS_URL
result_backend = settings.REDIS_URL

# Task settings
task_serializer = 'json'
result_serializer = 'json'
accept_content = ['json']
timezone = 'UTC'
enable_utc = True

# Task execution settings
task_acks_late = True
worker_prefetch_multiplier = 1
task_time_limit = 3600  # 1 hour hard limit
task_soft_time_limit = 3300  # 55 minutes soft limit

# Beat schedule
beat_schedule = {
    'check-secret-rotation': {
        'task': 'app.tasks.check_secret_rotation',
        'schedule': 3600.0,  # Every hour
    },
    'cleanup-expired-secrets': {
        'task': 'app.tasks.cleanup_expired_secrets',
        'schedule': 86400.0,  # Daily
    },
}

# Task routing
task_routes = {
    'app.tasks.rotate_secret': {'queue': 'secrets'},
    'app.tasks.check_secret_rotation': {'queue': 'secrets'},
    'app.tasks.cleanup_expired_secrets': {'queue': 'secrets'},
    'app.tasks.process_document': {'queue': 'documents'},
}

# Define queues
task_queues = (
    Queue('default', Exchange('default'), routing_key='default'),
    Queue('secrets', Exchange('secrets'), routing_key='secrets'),
    Queue('documents', Exchange('documents'), routing_key='documents'),
)

# Result settings
result_expires = 3600  # Results expire after 1 hour
result_persistent = True

# Worker settings
worker_max_tasks_per_child = 1000  # Restart worker after 1000 tasks
worker_disable_rate_limits = False

# Error handling
task_reject_on_worker_lost = True
task_ignore_result = False