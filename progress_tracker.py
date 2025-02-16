# progress_tracker.py
import threading


class ProgressTracker:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(ProgressTracker, cls).__new__(cls)
                    cls._instance.reset()
        return cls._instance

    def reset(self):
        self.progress = {
            'current': 0,
            'total': 0,
            'finished': False
        }

    def update(self, current, total, finished=False):
        with self._lock:
            self.progress['current'] = current
            self.progress['total'] = total
            self.progress['finished'] = finished

    def get_progress(self):
        with self._lock:
            return self.progress
