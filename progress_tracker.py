# progress_tracker.py

# Defines the structure and initial state for a download task's progress.
# This structure is serialized to Redis and used by the frontend.

def get_initial_progress_state():
    """Returns the initial dictionary representing a task's progress."""
    return {
        'starting': True,  # Indicates the download process is initializing
        'current': 0,  # Number of items processed so far
        'total': 0,  # Total number of items to process
        'finished': False,  # True if the download and processing (e.g., zipping) are complete
        'error': None,  # Stores an error message if one occurred
        'zip_ready': False  # True if the zip file has been created and is ready for download
    }


# Field names (can be used for consistency if needed)
FIELD_STARTING = 'starting'
FIELD_CURRENT = 'current'
FIELD_TOTAL = 'total'
FIELD_FINISHED = 'finished'
FIELD_ERROR = 'error'
FIELD_ZIP_READY = 'zip_ready'
