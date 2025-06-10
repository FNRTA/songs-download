# progress_tracker.py
import threading


class ProgressTracker:
    _lock = threading.Lock()

    def __init__(self):
        self.reset()  # Initialize progress on creation

    # Renamed original reset to _do_reset, assuming it's called when lock is held
    def _do_reset(self):
        self.progress = {
            'starting': True,
            'current': 0,
            'total': 0,
            'finished': False,
            'error': None,  # Added error field
            'zip_ready': False  # Flag to indicate zip is ready
        }

    # Public reset method that acquires the lock
    def reset(self):
        with self._lock:
            self._do_reset()

    def update(self, current=None, total=None, finished=False, error=None, zip_ready=False):
        with self._lock:
            # Only update starting if current or total is provided, 
            # allowing error updates without changing 'starting' flag prematurely.
            if current is not None or total is not None:
                self.progress['starting'] = False

            if current is not None:
                self.progress['current'] = current
            if total is not None:
                self.progress['total'] = total
            
            self.progress['finished'] = finished
            if zip_ready:
                self.progress['zip_ready'] = zip_ready
            if error:
                self.progress['error'] = error
                self.progress['finished'] = True  # Errors usually mean the task is finished

    def get_progress(self):
        with self._lock:
            # Make a copy to return the state *before* any potential reset
            progress_to_return = dict(self.progress)

            # If finished (either successfully or with an error), reset for the next operation.
            if self.progress['finished']:
                # Don't reset if zip is ready, cleanup is handled after download
                if not self.progress.get('zip_ready'):
                    self._do_reset()

            return progress_to_return
