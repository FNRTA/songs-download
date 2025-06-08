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
                    # Call the simple reset method, __new__ already holds the lock
                    cls._instance._do_reset()
        return cls._instance

    # Renamed original reset to _do_reset, assuming it's called when lock is held
    def _do_reset(self):
        self.progress = {
            'starting': True,
            'current': 0,
            'total': 0,
            'finished': False
        }

    # Public reset method that acquires the lock
    def reset(self):
        with self._lock:
            self._do_reset()

    def update(self, current, total, finished=False):
        with self._lock:
            self.progress['starting'] = False
            self.progress['current'] = current
            self.progress['total'] = total
            self.progress['finished'] = finished

    def get_progress(self):
        with self._lock:
            # Make a copy to return the state *before* any potential reset
            progress_to_return = dict(self.progress)

            if self.progress['finished']:
                # If finished, reset the state for the next operation.
                # We are already holding the lock, so call the internal reset.
                self._do_reset()

            return progress_to_return
