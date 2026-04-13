"""
Celery application configuration for async batch scoring.
Per PRD Section 6.1: >10,000 records/hour throughput for batch scoring.
"""

import os
from celery import Celery

# Redis as the broker and result backend
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/2")

celery_app = Celery(
    "credaly_batch_scoring",
    broker=REDIS_URL,
    backend=REDIS_URL,
)

celery_app.conf.update(
    # Task serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",

    # Timezone
    timezone="UTC",
    enable_utc=True,

    # Task execution
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_reject_on_worker_lost=True,

    # Result backend settings
    result_expires=3600,  # Results expire after 1 hour

    # Queue settings
    task_default_queue="batch_scoring",
    task_routes={
        "src.services.batch_scoring.tasks.score_batch_job": {
            "queue": "batch_scoring",
        },
    },

    # Retry settings
    task_default_retry_delay=60,
    task_default_max_retries=3,

    # Logging
    worker_log_format="[%(asctime)s: %(levelname)s/%(processName)s] %(message)s",
    worker_task_log_format="[%(asctime)s: %(levelname)s/%(processName)s] [%(task_name)s(%(task_id)s)] %(message)s",
)

# Auto-discover tasks
celery_app.autodiscover_tasks(["src.services.batch_scoring"])
