from flask import Flask, request, render_template, jsonify, send_from_directory, after_this_request
from deezer_downloader.client import DeezerClient
from deezer_downloader.config import DeezerConfig
from deezer_downloader.exceptions import DeezerException
import re
import uuid
import threading
import os
import shutil

app = Flask(__name__, template_folder='templates', static_folder='static')

# --- Constants and Setup ---

DOWNLOADS_DIR = os.path.join(app.root_path, 'downloads')
ZIPS_DIR = os.path.join(app.root_path, 'zips')

if not os.path.exists(DOWNLOADS_DIR):
    os.makedirs(DOWNLOADS_DIR)
if not os.path.exists(ZIPS_DIR):
    os.makedirs(ZIPS_DIR)

# --- Helper Functions ---

def validate_arl_cookie(arl_cookie):
    """Validates the ARL cookie."""
    arl_cookie_trimmed = arl_cookie.strip()
    if not arl_cookie_trimmed:
        return None, 'ARL cookie cannot be empty.'
    if not arl_cookie_trimmed.isalnum():  # Basic validation, can be more specific
        return None, 'ARL cookie must be alphanumeric.'
    return arl_cookie_trimmed, None


def parse_deezer_url(url):
    """Parses a Deezer URL to extract content type and ID."""
    url_match = re.match(r'https?://(?:www\.)?deezer\.com/(?:\w+/)?(\w+)/(\d+)', url)
    if not url_match:
        return None, None
    return url_match.groups()  # (content_type, content_id)


# --- Task Management ---

class TaskManager:
    """Manages download tasks and their progress trackers."""

    def __init__(self):
        self._tasks = {}
        self._lock = threading.Lock()  # For thread-safe access to _tasks

    def create_task(self, progress_tracker):
        """Creates a new task and returns its ID."""
        task_id = str(uuid.uuid4())
        with self._lock:
            self._tasks[task_id] = progress_tracker
        app.logger.info(f"Task {task_id} created.")
        return task_id

    def get_tracker(self, task_id):
        """Retrieves the progress tracker for a given task ID."""
        with self._lock:
            return self._tasks.get(task_id)

    def remove_task(self, task_id):
        """Removes a task and its tracker."""
        with self._lock:
            if task_id in self._tasks:
                del self._tasks[task_id]
                app.logger.info(f"Task {task_id} removed.")
                return True
        return False

    def cleanup_task_if_exists(self, task_id):
        """Removes a task if it exists, e.g., due to pre-thread error."""
        if self.get_tracker(task_id):  # Check existence before acquiring lock for removal
            self.remove_task(task_id)
            app.logger.info(f"Cleaned up tracker for task {task_id} due to pre-thread error.")


task_manager = TaskManager()


# --- Background Download Logic ---

def _execute_download_in_background(client, content_type, content_id, task_id):
    """Target function for the download thread."""
    tracker = task_manager.get_tracker(task_id)
    if not tracker:
        app.logger.error(f"_execute_download_in_background: Tracker not found for task_id {task_id}")
        return

    download_actions = {
        'track': client.download_track,
        'album': client.download_album,
        'playlist': client.download_playlist,
    }

    action = download_actions.get(content_type)
    task_download_dir = client.config.download_folder

    try:
        if action:
            action(content_id)
            # All files for the task are now in task_download_dir
            zip_filename = f"{task_id}.zip"
            zip_path = os.path.join(ZIPS_DIR, zip_filename)

            # Create zip from the task's download directory
            shutil.make_archive(os.path.join(ZIPS_DIR, task_id), 'zip', task_download_dir)
            app.logger.info(f"Task {task_id}: Successfully created zip archive at {zip_path}")

            # Clean up the original download directory
            shutil.rmtree(task_download_dir)
            app.logger.info(f"Task {task_id}: Cleaned up source directory {task_download_dir}")

            # Update tracker with finished status and zip path
            tracker.update(finished=True, zip_ready=True)

        else:
            # This case should be caught by pre-thread validation in /download
            err_msg = f'Unsupported content type in thread: {content_type}'
            app.logger.error(err_msg)
            tracker.update(finished=True, error=err_msg)
            # Task will be cleaned up by /progress or if it never gets polled
            return
        # DeezerClient methods should set finished=True on completion.

    except DeezerException as e:
        app.logger.error(f"DeezerException in background task {task_id}: {str(e)}")
        tracker.update(finished=True, error=str(e))
    except Exception as e:
        app.logger.error(f"Unexpected exception in background task {task_id}: {str(e)}")
        tracker.update(finished=True, error='An unexpected server error occurred during download.')
    # The /progress route will handle cleanup of the tracker from task_manager


# --- Routes ---

@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')

@app.route('/download', methods=['POST'])
def download():
    app.logger.info("Received download request")
    arl_cookie_form = request.form.get('arl_cookie', '')
    url_form = request.form.get('url', '')

    arl_cookie, error_msg = validate_arl_cookie(arl_cookie_form)
    if error_msg:
        return jsonify({'error': error_msg}), 400

    if not url_form:
        return jsonify({'error': 'URL cannot be empty.'}), 400

    content_type, content_id = parse_deezer_url(url_form)
    if not content_type or not content_id:
        return jsonify({'error': 'Invalid Deezer URL'}), 400

    if content_type not in ['track', 'album', 'playlist']:
        return jsonify({'error': f'Unsupported content type: {content_type}'}), 400

    config = DeezerConfig(cookie_arl=arl_cookie)
    client = DeezerClient(config)
    try:
        client.initialize()
        app.logger.info('DeezerClient initialized')
    except Exception as e:
        app.logger.error(f"Failed to initialize DeezerClient: {str(e)}")
        return jsonify({'error': f'Failed to initialize Deezer session: {str(e)}'}), 500

    if not hasattr(client, 'progress_tracker') or client.progress_tracker is None:
        app.logger.error(f"DeezerClient does not have a progress_tracker after initialization.")
        return jsonify({'error': 'Failed to set up progress tracking for the task.'}), 500

    task_id = task_manager.create_task(client.progress_tracker)
    app.logger.info(f'Task {task_id} created for {content_type}/{content_id}')

    # Create a unique download folder for this task
    task_download_path = os.path.join(DOWNLOADS_DIR, task_id)
    if not os.path.exists(task_download_path):
        os.makedirs(task_download_path)

    config = DeezerConfig(cookie_arl=arl_cookie, download_folder=task_download_path)
    client = DeezerClient(config)
    try:
        client.initialize()
        app.logger.info('DeezerClient initialized')
    except Exception as e:
        app.logger.error(f"Failed to initialize DeezerClient: {str(e)}")
        return jsonify({'error': f'Failed to initialize Deezer session'}), 500

    task_manager._tasks[task_id] = client.progress_tracker  # Associate tracker with the task

    thread = threading.Thread(target=_execute_download_in_background,
                              args=(client, content_type, content_id, task_id))
    thread.daemon = True
    thread.start()

    return jsonify({'success': True, 'task_id': task_id})

@app.route('/progress', methods=['GET'])
def progress():
    task_id = request.args.get('task_id')
    if not task_id:
        return jsonify({'error': 'Task ID is required', 'finished': True}), 400

    tracker = task_manager.get_tracker(task_id)
    if not tracker:
        # This could mean the task finished and was cleaned up, or an invalid/old task_id
        return jsonify({'error': 'Progress not found. Task may have finished or an error occurred.',
                        'finished': True}), 404

    progress_data = tracker.get_progress()

    return jsonify(progress_data)


@app.route('/download_zip/<task_id>', methods=['GET'])
def download_zip(task_id):
    """Serves the zipped download archive and cleans up afterwards."""
    # Validate task_id by checking for tracker existence. This prevents path injection.
    tracker = task_manager.get_tracker(task_id)
    if not tracker:
        return jsonify({'error': 'Task not found, invalid, or already cleaned up.'}), 404

    # Construct filename from the validated task_id and check if it exists.
    zip_filename = f"{task_id}.zip"
    zip_path = os.path.join(ZIPS_DIR, zip_filename)

    if not os.path.exists(zip_path):
        return jsonify({'error': 'Zip file not found or not ready.'}), 404

    @after_this_request
    def cleanup_after_request(response):
        try:
            task_manager.remove_task(task_id)
            app.logger.info(f"Cleaned up finished task {task_id} from progress route.")

            if os.path.exists(zip_path):
                os.remove(zip_path)
                app.logger.info(f"Cleaned up zip file: {zip_path}")
            task_manager.remove_task(task_id)
            app.logger.info(f"Cleaned up task {task_id} after zip download.")
        except Exception as e:
            app.logger.error(f"Error during cleanup for task {task_id}: {e}")
        return response

    return send_from_directory(ZIPS_DIR, zip_filename, as_attachment=True)

if __name__ == '__main__':
    app.run(debug=False)  # Set debug=True for development if needed, False for production
