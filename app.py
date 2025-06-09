from flask import Flask, request, render_template, jsonify
from deezer_downloader.client import DeezerClient
from deezer_downloader.config import DeezerConfig
from deezer_downloader.exceptions import DeezerException
import re
import uuid
import threading

app = Flask(__name__, template_folder='templates', static_folder='static')

# Dictionary to store progress trackers for each task
task_progress_trackers = {}

def _execute_download_in_background(client, content_type, content_id, task_id):
    """Target function for the download thread."""
    tracker = task_progress_trackers.get(task_id)
    if not tracker:  # Should not happen if called correctly
        app.logger.error(f"_execute_download_in_background: Tracker not found for task_id {task_id}")
        return

    try:
        if content_type == 'track':
            client.download_track(content_id)
        elif content_type == 'album':
            client.download_album(content_id)
        elif content_type == 'playlist':
            client.download_playlist(content_id)
        else:
            # This case should ideally be caught before starting the thread,
            # but as a safeguard:
            err_msg = f'Unsupported content type in thread: {content_type}'
            app.logger.error(err_msg)
            if hasattr(tracker, 'update'):  # Check if tracker has an 'update' method that can take 'error'
                tracker.update(finished=True, error=err_msg)  # Assumes ProgressTracker is updated to handle 'error'
            if task_id in task_progress_trackers: del task_progress_trackers[task_id]
            return
        # If download methods complete without raising an exception that sets 'finished', ensure it's set.
        # DeezerClient methods already set finished=True on completion.

    except DeezerException as e:
        app.logger.error(f"DeezerException in background task {task_id}: {str(e)}")
        if hasattr(tracker, 'update'):
            tracker.update(finished=True, error=str(e))  # Assumes ProgressTracker handles 'error'
        # The /progress route will handle cleanup of the tracker from task_progress_trackers
    except Exception as e:
        app.logger.error(f"Unexpected exception in background task {task_id}: {str(e)}")
        if hasattr(tracker, 'update'):
            tracker.update(finished=True, error='An unexpected server error occurred during download.')
        # The /progress route will handle cleanup

@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')

@app.route('/download', methods=['POST'])
def download():
    app.logger.info("Received download request")
    arl_cookie = request.form['arl_cookie']
    url = request.form['url']

    arl_cookie_trimmed = arl_cookie.strip()
    if not arl_cookie_trimmed:
        return jsonify({'error': 'ARL cookie cannot be empty.'}), 400
    if not arl_cookie_trimmed.isalnum():
        return jsonify({'error': 'ARL cookie must be alphanumeric.'}), 400

    config = DeezerConfig(cookie_arl=arl_cookie_trimmed)
    client = DeezerClient(config)
    try:
        client.initialize()  # Keep initialization in the main thread
        app.logger.info('DeezerClient initialized')
    except Exception as e:
        app.logger.error(f"Failed to initialize DeezerClient: {str(e)}")
        return jsonify({'error': f'Failed to initialize Deezer session: {str(e)}'}), 500

    task_id = str(uuid.uuid4())
    app.logger.info('TaskId created')
    # Ensure ProgressTracker instance from client is stored
    if not hasattr(client, 'progress_tracker') or client.progress_tracker is None:
        app.logger.error(f"DeezerClient for task {task_id} does not have a progress_tracker.")
        return jsonify({'error': 'Failed to set up progress tracking for the task.'}), 500
    task_progress_trackers[task_id] = client.progress_tracker

    url_match = re.match(r'https?://(?:www\.)?deezer\.com/(?:\w+/)?(\w+)/(\d+)', url)
    if not url_match:
        if task_id in task_progress_trackers: del task_progress_trackers[task_id]
        return jsonify({'error': 'Invalid Deezer URL'}), 400

    content_type, content_id = url_match.groups()

    # Validate content_type before starting thread
    if content_type not in ['track', 'album', 'playlist']:
        if task_id in task_progress_trackers: del task_progress_trackers[task_id]
        return jsonify({'error': f'Unsupported content type: {content_type}'}), 400

    # Start the download in a background thread
    thread = threading.Thread(target=_execute_download_in_background,
                              args=(client, content_type, content_id, task_id))
    thread.daemon = True  # Allows main program to exit even if threads are still running
    thread.start()

    # Return task_id immediately
    return jsonify({'success': True, 'task_id': task_id})

@app.route('/progress', methods=['GET'])
def progress():
    task_id = request.args.get('task_id')
    if not task_id:
        return jsonify({'error': 'Task ID is required', 'finished': True}), 400

    tracker = task_progress_trackers.get(task_id)
    if not tracker:
        return jsonify({'error': 'Progress not found for this task. It may have finished or an error occurred.',
                        'finished': True}), 404

    progress_data = tracker.get_progress()

    if progress_data.get('finished'):
        if task_id in task_progress_trackers:
            del task_progress_trackers[task_id]

    return jsonify(progress_data)

if __name__ == '__main__':
    app.run(debug=False)
