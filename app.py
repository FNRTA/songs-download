from flask import Flask, request, render_template, jsonify, send_from_directory, after_this_request
from deezer_downloader.client import DeezerClient
from deezer_downloader.config import DeezerConfig
from deezer_downloader.exceptions import DeezerException
import re
import threading
import os
import shutil
import tempfile
from datetime import datetime, timedelta
from redis_manager import RedisManager
from progress_tracker import FIELD_FINISHED, FIELD_ERROR, FIELD_ZIP_READY

app = Flask(__name__, template_folder='templates', static_folder='static')

# --- Environment Configuration ---
ENV = os.environ.get('FLASK_ENV', 'development').lower()

if ENV == 'development':
    # In development, use a local directory (e.g., 'project_root/dl')
    BASE_TEMP_DIR = os.path.join(app.root_path, 'dl')
else:
    # In production (or default), use the system's temporary directory
    BASE_TEMP_DIR = os.path.join(tempfile.gettempdir(), 'deezer_dl_redis')

DOWNLOADS_DIR = os.path.join(BASE_TEMP_DIR, 'downloads')
ZIPS_DIR = os.path.join(BASE_TEMP_DIR, 'zips')

# Ensure directories exist
os.makedirs(DOWNLOADS_DIR, exist_ok=True)
os.makedirs(ZIPS_DIR, exist_ok=True)

app.logger.info(f"ENV: {ENV}, Base data directory: {BASE_TEMP_DIR}")
app.logger.info(f"Downloads directory: {DOWNLOADS_DIR}")
app.logger.info(f"Zips directory: {ZIPS_DIR}")

# --- Redis Manager and Task Manager Initialization ---
redis_manager = RedisManager(redis_url=os.environ.get('REDIS_URL'))


def cleanup_old_files(directory, max_age_hours=24):
    """Clean up files/directories older than max_age_hours in a given directory."""
    if not os.path.exists(directory):
        return
    now = datetime.now()

    if len(os.listdir(directory)) == 0:
        app.logger.info(f"General cleanup: No files to clean up in {directory}")
        return

    for item_name in os.listdir(directory):
        item_path = os.path.join(directory, item_name)
        try:
            item_mtime = datetime.fromtimestamp(os.path.getmtime(item_path))
            if now - item_mtime > timedelta(hours=max_age_hours):
                if os.path.isfile(item_path):
                    os.remove(item_path)
                    app.logger.info(f"General cleanup: Removed old file {item_path}")
                elif os.path.isdir(item_path):
                    shutil.rmtree(item_path, ignore_errors=True)
                    app.logger.info(f"General cleanup: Removed old directory {item_path}")
        except Exception as e:
            app.logger.error(f"General cleanup: Error processing {item_path}: {e}")


# General cleanup on startup (can be disabled if TaskManager's cleanup is sufficient)
cleanup_old_files(DOWNLOADS_DIR, max_age_hours=1)
cleanup_old_files(ZIPS_DIR, max_age_hours=1)

# --- Helper Functions ---

def validate_arl_cookie(arl_cookie):
    """Validates the ARL cookie."""
    arl_cookie_trimmed = arl_cookie.strip()
    if not arl_cookie_trimmed:
        return None, 'ARL cookie cannot be empty.'
    if not arl_cookie_trimmed.isalnum():  
        return None, 'ARL cookie must be alphanumeric.'
    return arl_cookie_trimmed, None


def parse_deezer_url(url):
    """Parses a Deezer URL to extract content type and ID."""
    url_match = re.match(r'https?://(?:www\.)?deezer\.com/(?:\w+/)?(\w+)/(\d+)', url)
    if not url_match:
        return None, None
    return url_match.groups()  


# --- Task Management ---

class TaskManager:
    """Manages download tasks using RedisManager and handles file system cleanup."""

    def __init__(self, redis_manager_instance: RedisManager):
        self.redis_manager = redis_manager_instance
        self.cleanup_interval_seconds = 3600
        self._stop_cleanup_event = threading.Event()
        self._cleanup_thread = threading.Thread(target=self._cleanup_stale_task_files_periodically, daemon=True)
        self._cleanup_thread.start()
        app.logger.info("TaskManager initialized with RedisManager and cleanup thread started.")

    def create_task_for_download(self) -> str:
        """Creates a new task entry in Redis and returns its ID."""
        task_id = self.redis_manager.create_task()
        app.logger.info(f"Task {task_id} created in Redis.")
        return task_id

    def get_task_progress(self, task_id: str):
        """Retrieves the progress for a given task ID from Redis."""
        return self.redis_manager.get_task_progress(task_id)

    def update_task_progress(self, task_id: str, **updates):
        """Updates the progress for a task in Redis."""
        return self.redis_manager.update_task_progress(task_id, **updates)

    def remove_task_data(self, task_id: str):
        """Removes a task's data from Redis and cleans up associated local files."""
        task_download_dir = os.path.join(DOWNLOADS_DIR, task_id)
        zip_file_path = os.path.join(ZIPS_DIR, f"{task_id}.zip")

        if os.path.exists(task_download_dir):
            try:
                shutil.rmtree(task_download_dir)
                app.logger.info(f"Removed download directory: {task_download_dir}")
            except Exception as e:
                app.logger.error(f"Error removing download directory {task_download_dir}: {e}")

        if os.path.exists(zip_file_path):
            try:
                os.remove(zip_file_path)
                app.logger.info(f"Removed zip file: {zip_file_path}")
            except Exception as e:
                app.logger.error(f"Error removing zip file {zip_file_path}: {e}")

        removed_from_redis = self.redis_manager.remove_task(task_id)
        if removed_from_redis:
            app.logger.info(f"Task {task_id} removed from Redis.")
        else:
            app.logger.warning(f"Attempted to remove task {task_id} from Redis, but it was not found.")

    def _cleanup_stale_task_files_periodically(self):
        """Periodically scans for and cleans up orphaned task files."""
        app.logger.info("Task file cleanup thread started.")
        while not self._stop_cleanup_event.is_set():
            try:
                # Check DOWNLOADS_DIR for orphaned task directories
                if os.path.exists(DOWNLOADS_DIR):
                    for item_name in os.listdir(DOWNLOADS_DIR):
                        item_path = os.path.join(DOWNLOADS_DIR, item_name)
                        if os.path.isdir(item_path):
                            # Assuming item_name is a task_id
                            task_id = item_name
                            if self.redis_manager.get_task_progress(task_id) is None:
                                app.logger.info(
                                    f"Cleanup thread: Found orphaned download dir for task {task_id}. Removing.")
                                self.remove_task_data(task_id)

                                # Check ZIPS_DIR for orphaned zip files
                if os.path.exists(ZIPS_DIR):
                    for item_name in os.listdir(ZIPS_DIR):
                        if item_name.endswith('.zip'):
                            task_id = item_name[:-4]
                            if self.redis_manager.get_task_progress(task_id) is None:
                                app.logger.info(
                                    f"Cleanup thread: Found orphaned zip file for task {task_id}. Removing.")
                                self.remove_task_data(task_id)

            except Exception as e:
                app.logger.error(f"Error in cleanup thread: {e}")

            self._stop_cleanup_event.wait(self.cleanup_interval_seconds)
        app.logger.info("Task file cleanup thread stopped.")

    def stop_cleanup_thread(self):
        app.logger.info("Attempting to stop cleanup thread...")
        self._stop_cleanup_event.set()
        if self._cleanup_thread.is_alive():
            self._cleanup_thread.join(timeout=5)
        if self._cleanup_thread.is_alive():
            app.logger.warning("Cleanup thread did not stop in time.")
        else:
            app.logger.info("Cleanup thread stopped successfully.")


task_manager = TaskManager(redis_manager)

# Graceful shutdown
import atexit

atexit.register(task_manager.stop_cleanup_thread)

# --- Background Download Logic ---

def _execute_download_in_background(arl_cookie, content_type_val, content_id_val, task_id):
    """Target function for the download thread, uses Redis for progress."""
    app.logger.info(f"Starting background download for task {task_id}: {content_type_val}/{content_id_val}")

    task_specific_download_dir = os.path.join(DOWNLOADS_DIR, task_id)
    try:
        os.makedirs(task_specific_download_dir, exist_ok=True)
    except Exception as e:
        app.logger.error(f"Failed to create download directory {task_specific_download_dir} for task {task_id}: {e}")
        task_manager.update_task_progress(task_id,
                                          **{FIELD_ERROR: 'Failed to create download directory.', FIELD_FINISHED: True})
        return

    config = DeezerConfig(cookie_arl=arl_cookie, download_folder=task_specific_download_dir)
    client = DeezerClient(config=config, redis_manager=task_manager.redis_manager, task_id=task_id)
    client.initialize()

    download_actions = {
        'track': client.download_track,
        'album': client.download_album,
        'playlist': client.download_playlist,
    }
    action = download_actions.get(content_type_val)

    try:
        if not action:
            err_msg = f'Unsupported content type in thread: {content_type_val}'
            app.logger.error(err_msg)
            task_manager.update_task_progress(task_id, **{FIELD_ERROR: err_msg, FIELD_FINISHED: True})
            return

        downloaded_file_paths = action(content_id_val)

        if not downloaded_file_paths:
            app.logger.info(
                f"Task {task_id}: No files were downloaded by the client (e.g., empty playlist or all tracks failed).")
            task_manager.update_task_progress(task_id,
                                              **{FIELD_ERROR: 'No files were downloaded.', FIELD_FINISHED: True})
            shutil.rmtree(task_specific_download_dir)
            return

        app.logger.info(f"Task {task_id}: Download client finished. {len(downloaded_file_paths)} items processed.")

        zip_filename_base = task_id
        zip_archive_path_base = os.path.join(ZIPS_DIR, zip_filename_base)

        app.logger.info(
            f"Task {task_id}: Attempting to create zip archive from {task_specific_download_dir} to {zip_archive_path_base}.zip")
        shutil.make_archive(zip_archive_path_base, 'zip', root_dir=task_specific_download_dir)
        app.logger.info(f"Task {task_id}: Successfully created zip archive at {zip_archive_path_base}.zip")

        task_manager.update_task_progress(task_id, **{FIELD_ZIP_READY: True, FIELD_FINISHED: True})
        app.logger.info(f"Task {task_id}: Progress updated - zip ready and finished.")

    except DeezerException as e:
        app.logger.error(f"DeezerException in background task {task_id}: {str(e)}")
        task_manager.update_task_progress(task_id, **{FIELD_ERROR: str(e), FIELD_FINISHED: True})
    except Exception as e:
        app.logger.error(f"Unexpected exception in background task {task_id}: {str(e)}", exc_info=True)
        task_manager.update_task_progress(task_id,
                                          **{FIELD_ERROR: 'An unexpected server error occurred during processing.',
                                             FIELD_FINISHED: True})
    finally:
        if os.path.exists(task_specific_download_dir):
            try:
                shutil.rmtree(task_specific_download_dir)
                app.logger.info(f"Task {task_id}: Cleaned up source directory {task_specific_download_dir}")
            except Exception as e:
                app.logger.error(
                    f"Task {task_id}: Error cleaning up source directory {task_specific_download_dir}: {e}")

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

    try:
        task_id = task_manager.create_task_for_download()
    except Exception as e:
        app.logger.error(f"Failed to create task in Redis: {e}")
        return jsonify({'error': 'Failed to initiate download task. Please try again.'}), 500

    app.logger.info(f"Download request validated. Task ID: {task_id}. Starting background thread.")
    thread = threading.Thread(target=_execute_download_in_background, args=(
        arl_cookie, content_type, content_id, task_id
    ))
    thread.start()

    return jsonify({'success': True, 'task_id': task_id})


@app.route('/progress', methods=['GET'])
def progress():
    task_id = request.args.get('task_id')
    progress_data = task_manager.get_task_progress(task_id)

    if progress_data is None:
        zip_file_path = os.path.join(ZIPS_DIR, f"{task_id}.zip")
        if os.path.exists(zip_file_path):
            return jsonify({'error': 'Task data not found but zip exists. Please try downloading the zip.',
                            'zip_potentially_available': True}), 404
        return jsonify({'error': 'Task not found or has expired.', 'finished': True,
                        'error': 'Task not found or has expired.'}), 404
    
    return jsonify(progress_data)


@app.route('/download_zip/<task_id>', methods=['GET'])
def download_zip(task_id):
    app.logger.info(f"Received download_zip request for task_id: {task_id}")
    progress_data = task_manager.get_task_progress(task_id)

    if progress_data is None:
        return jsonify({'error': 'Task not found or has expired.'}), 404

    if not progress_data.get(FIELD_ZIP_READY):
        err_msg = 'Zip file is not ready.'
        if progress_data.get(FIELD_ERROR):
            err_msg = f"Download failed: {progress_data.get(FIELD_ERROR)}"
        elif not progress_data.get(FIELD_FINISHED):
            err_msg = 'Download is still in progress.'
        return jsonify({'error': err_msg}), 400 

    zip_filename = f"{task_id}.zip"
    zip_file_full_path = os.path.join(ZIPS_DIR, zip_filename)

    if not os.path.exists(zip_file_full_path):
        app.logger.error(
            f"Zip file {zip_file_full_path} not found on disk for task {task_id}, though Redis reported zip_ready.")
        task_manager.update_task_progress(task_id,
                                          **{FIELD_ERROR: 'Zip file missing on server.', FIELD_ZIP_READY: False})
        return jsonify({'error': 'Zip file not found on server. Please try the download again.'}), 404

    @after_this_request
    def cleanup_files_after_request(response):
        app.logger.info(f"Cleaning up task data for {task_id} after zip download.")
        try:
            task_manager.remove_task_data(task_id)
        except Exception as e:
            app.logger.error(f"Error during post-download cleanup for task {task_id}: {e}")
        return response

    app.logger.info(f"Sending zip file {zip_filename} for task {task_id}")
    return send_from_directory(ZIPS_DIR, zip_filename, as_attachment=True)


if __name__ == '__main__':
    app.run(debug=False)
