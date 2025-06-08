from flask import Flask, request, render_template_string, jsonify
from deezer_downloader.client import DeezerClient
from deezer_downloader.config import DeezerConfig
from deezer_downloader.exceptions import DeezerException
import re
import uuid
import threading

app = Flask(__name__)

# Dictionary to store progress trackers for each task
task_progress_trackers = {}

# Define the HTML template for the web interface
template = """
<html>
  <head>
    <title>Deezer Downloader</title>
    <style>
      body {
        font-family: Arial, sans-serif;
        background-color: #f0f0f0;
      }
      .container {
        max-width: 400px;
        margin: 40px auto;
        padding: 20px;
        background-color: #fff;
        border: 1px solid #ddd;
        border-radius: 10px;
        box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
      }
      .header {
        text-align: center;
        margin-bottom: 20px;
      }
      .header h1 {
        font-size: 24px;
        margin-top: 0;
      }
      .form-group {
        margin-bottom: 20px;
      }
      .form-group label {
        display: block;
        margin-bottom: 10px;
      }
      .form-group input {
        width: 100%;
        height: 40px;
        padding: 10px;
        font-size: 16px;
        border: 1px solid #ccc;
        border-radius: 5px;
      }
      .form-group input:focus {
        border-color: #aaa;
        box-shadow: 0 0 5px rgba(0, 0, 0, 0.2);
      }
      .button {
        width: 100%;
        height: 40px;
        padding: 10px;
        font-size: 16px;
        background-color: #4CAF50;
        color: #fff;
        border: none;
        border-radius: 5px;
        cursor: pointer;
      }
      .button:disabled {
        background-color: #ccc;
        cursor: not-allowed;
      }
      .progress {
        margin-top: 10px;
        text-align: center;
      }
      .finished {
        color: green;
        font-weight: bold;
        margin-top: 10px;
        text-align: center;
      }
      /* Snackbar CSS */
      #snackbar {
        visibility: hidden;
        min-width: 250px;
        margin-left: -125px;
        background-color: #f44336; /* Red for errors */
        color: white;
        text-align: center;
        border-radius: 2px;
        padding: 16px;
        position: fixed;
        z-index: 1;
        left: 50%;
        top: 30px;
        font-size: 17px;
      }

      #snackbar.show {
        visibility: visible;
        -webkit-animation: fadein 0.5s, fadeout 0.5s 2.5s;
        animation: fadein 0.5s, fadeout 0.5s 2.5s;
      }

      @-webkit-keyframes fadein {
        from {top: 0; opacity: 0;}
        to {top: 30px; opacity: 1;}
      }

      @keyframes fadein {
        from {top: 0; opacity: 0;}
        to {top: 30px; opacity: 1;}
      }

      @-webkit-keyframes fadeout {
        from {top: 30px; opacity: 1;}
        to {top: 0; opacity: 0;}
      }

      @keyframes fadeout {
        from {top: 30px; opacity: 1;}
        to {top: 0; opacity: 0;}
      }
    </style>
    <script>
      document.addEventListener('DOMContentLoaded', (event) => {
        const storedArlCookie = localStorage.getItem('arlCookieValue');
        if (storedArlCookie) {
          document.getElementById('arl_cookie').value = storedArlCookie;
        }
      });

      let currentInterval = null;
      let currentTaskId = null;

      function startDownload() {
        const button = document.querySelector('.button');
        const progress = document.querySelector('.progress');
        const finished = document.querySelector('.finished');
        const form = document.querySelector('form');
        const arlCookieInput = document.getElementById('arl_cookie');

        if (arlCookieInput && arlCookieInput.value) {
          localStorage.setItem('arlCookieValue', arlCookieInput.value);
        }

        button.disabled = true;
        progress.style.display = 'block';
        finished.style.display = 'none';

        const formData = new FormData(form);
        
        if (currentInterval) {
          clearInterval(currentInterval);
          currentInterval = null;
        }
        currentTaskId = null;

        fetch('/download', {
          method: 'POST',
          body: formData
        })
        .then(response => response.json())
        .then(data => {
          if (data.error) {
            showSnackbar(data.error);
            button.disabled = false;
            progress.style.display = 'none';
            return;
          }

          if (data.task_id) {
            currentTaskId = data.task_id;

            currentInterval = setInterval(() => {
              if (!currentTaskId) {
                clearInterval(currentInterval);
                currentInterval = null;
                button.disabled = false;
                progress.style.display = 'none';
                return;
              }

              fetch(`/progress?task_id=${currentTaskId}`)
                .then(response => response.json())
                .then(progressData => {
                  if (progressData.error) {
                    showSnackbar(progressData.error);
                    clearInterval(currentInterval);
                    currentInterval = null;
                    button.disabled = false;
                    progress.style.display = 'none';
                    currentTaskId = null;
                    return;
                  }

                  if (progressData.starting) {
                    progress.textContent = 'Download starting...';
                  } else if (progressData.finished) {
                    clearInterval(currentInterval);
                    currentInterval = null;
                    button.disabled = false;
                    progress.style.display = 'none';
                    finished.style.display = 'block';
                    finished.textContent = 'Download finished!';
                    currentTaskId = null;
                  } else {
                    progress.textContent = `Downloading ${progressData.current}/${progressData.total}`;
                  }
                })
                .catch(error => {
                    console.error('Error fetching progress:', error);
                    showSnackbar('Error checking download status.');
                    clearInterval(currentInterval);
                    currentInterval = null;
                    button.disabled = false;
                    progress.style.display = 'none';
                    currentTaskId = null;
                });
            }, 2000);
          } else {
            showSnackbar('Error: No task ID received from server.');
            button.disabled = false;
            progress.style.display = 'none';
          }
        })
        .catch(error => {
            console.error('Error initiating download:', error);
            showSnackbar('Network or server error during download request.');
            button.disabled = false;
            progress.style.display = 'none';
            if (currentInterval) {
                clearInterval(currentInterval);
                currentInterval = null;
            }
            currentTaskId = null;
        });
      }
      
      function showSnackbar(message) {
        const snackbar = document.getElementById("snackbar");
        snackbar.textContent = message;
        snackbar.className = "show";
        setTimeout(function(){ snackbar.className = snackbar.className.replace("show", ""); }, 3000);
      }
    </script>
  </head>
  <body>
    <div id="snackbar">Some text some message..</div> 
    <div class="container">
      <div class="header">
        <h1>Deezer Downloader</h1>
      </div>
      <form onsubmit="event.preventDefault(); startDownload();">
        <div class="form-group">
          <label for="arl_cookie">ARL Cookie:</label>
          <input type="text" id="arl_cookie" name="arl_cookie">
        </div>
        <div class="form-group">
          <label for="url">Deezer URL:</label>
          <input type="text" id="url" name="url">
        </div>
        <button class="button" type="submit">Download</button>
        <div class="progress" style="display: none;"></div>
        <div class="finished" style="display: none;"></div>
      </form>
    </div>
  </body>
</html>
"""


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
    return render_template_string(template)

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
    except Exception as e:
        app.logger.error(f"Failed to initialize DeezerClient: {str(e)}")
        return jsonify({'error': f'Failed to initialize Deezer session: {str(e)}'}), 500

    task_id = str(uuid.uuid4())
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
