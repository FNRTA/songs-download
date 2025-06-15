import os
import redis
import uuid
from datetime import timedelta
from typing import Optional, Dict, Any
from progress_tracker import get_initial_progress_state, FIELD_CURRENT, FIELD_TOTAL, FIELD_STARTING, FIELD_FINISHED, \
    FIELD_ZIP_READY, FIELD_ERROR


class RedisManager:
    """Manages download task progress using Redis."""

    def __init__(self, redis_url: Optional[str] = None, expire_hours: int = 2):
        if redis_url is None:
            redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
        self.redis = redis.Redis.from_url(redis_url, decode_responses=True)
        self.namespace = 'dz-dl/'  # Updated namespace
        self.expire_hours = expire_hours

    def _get_key(self, task_id: str) -> str:
        return f"{self.namespace}{task_id}"

    def create_task(self) -> str:
        """Creates a new task, stores its initial progress in Redis, and returns its ID."""
        task_id = str(uuid.uuid4())
        initial_progress = get_initial_progress_state()
        self._set_task_progress_in_redis(task_id, initial_progress)
        return task_id

    def get_task_progress(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves the progress dictionary for a given task ID from Redis."""
        key = self._get_key(task_id)
        raw_data = self.redis.hgetall(key)

        if not raw_data:
            return None

        # Initialize with default structure for safety, then populate
        progress: Dict[str, Any] = get_initial_progress_state()

        # Convert string values from Redis to appropriate Python types
        if FIELD_CURRENT in raw_data:
            progress[FIELD_CURRENT] = int(raw_data[FIELD_CURRENT])
        if FIELD_TOTAL in raw_data:
            progress[FIELD_TOTAL] = int(raw_data[FIELD_TOTAL])

        for bool_field in [FIELD_STARTING, FIELD_FINISHED, FIELD_ZIP_READY]:
            if bool_field in raw_data:
                progress[bool_field] = raw_data[bool_field] == 'True'

        if FIELD_ERROR in raw_data:
            progress[FIELD_ERROR] = None if raw_data[FIELD_ERROR] == 'None' else raw_data[FIELD_ERROR]

        return progress

    def update_task_progress(self, task_id: str, **updates: Any) -> bool:
        """Updates the progress dictionary for a task in Redis."""
        current_progress = self.get_task_progress(task_id)
        if current_progress is None:
            # Task not found or expired
            return False

        current_progress.update(updates)
        self._set_task_progress_in_redis(task_id, current_progress)
        return True

    def _set_task_progress_in_redis(self, task_id: str, progress_data: Dict[str, Any]):
        """Serializes progress data to strings and stores it in a Redis hash."""
        key = self._get_key(task_id)
        # Convert all values to strings for Redis hmset
        redis_data = {k: str(v) for k, v in progress_data.items()}

        # Use a pipeline for atomicity of hmset and expire
        pipe = self.redis.pipeline()
        pipe.hmset(key, redis_data)
        if self.expire_hours > 0:
            pipe.expire(key, int(timedelta(hours=self.expire_hours).total_seconds()))
        pipe.execute()

    def remove_task(self, task_id: str) -> bool:
        """Removes a task and its progress data from Redis."""
        key = self._get_key(task_id)
        deleted_count = self.redis.delete(key)
        return deleted_count > 0

# No global instance here; it will be created in app.py or where needed.
