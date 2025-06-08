from flask import Flask, request, render_template_string, jsonify
from deezer_downloader.client import DeezerClient
from deezer_downloader.config import DeezerConfig
from deezer_downloader.exceptions import DeezerException
import re
import uuid

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

        // Store ARL cookie in localStorage
        if (arlCookieInput && arlCookieInput.value) {
          localStorage.setItem('arlCookieValue', arlCookieInput.value);
        }

        button.disabled = true;
        progress.style.display = 'block';
        finished.style.display = 'none';

        const formData = new FormData(form);
        
        // Clear previous interval if any
        if (currentInterval) {
          clearInterval(currentInterval);
          currentInterval = null;
        }
        currentTaskId = null; 

        // Start polling for progress
        currentInterval = setInterval(() => {
          if (!currentTaskId) { 
            return;
          }
          fetch(`/progress?task_id=${currentTaskId}`)
            .then(response => response.json())
            .then(data => {
              if (data.error) {
                showSnackbar(data.error);
                clearInterval(currentInterval);
                currentInterval = null;
                button.disabled = false;
                progress.style.display = 'none';
                currentTaskId = null;
                return;
              }

              if (data.starting) {
                progress.textContent = 'Download starting...';
              } else if (data.finished) {
                clearInterval(currentInterval);
                currentInterval = null;
                button.disabled = false;
                progress.style.display = 'none';
                finished.style.display = 'block';
                finished.textContent = 'Download finished!';
                currentTaskId = null; 
              } else {
                progress.textContent = `Downloading ${data.current}/${data.total}`;
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
            if (currentInterval) {
              clearInterval(currentInterval);
              currentInterval = null;
            }
            return;
          }
          // Store the task_id from the response
          if (data.task_id) {
            currentTaskId = data.task_id;
          } else {
            showSnackbar('Error: No task ID received from server.');
            button.disabled = false;
            progress.style.display = 'none';
            if (currentInterval) {
              clearInterval(currentInterval);
              currentInterval = null;
            }
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

@app.route('/', methods=['GET'])
def index():
    return render_template_string(template)

@app.route('/download', methods=['POST'])
def download():
    arl_cookie = request.form['arl_cookie']
    url = request.form['url']

    arl_cookie_trimmed = arl_cookie.strip()
    if not arl_cookie_trimmed:
        return jsonify({'error': 'ARL cookie cannot be empty.'}), 400
    if not arl_cookie_trimmed.isalnum():
        return jsonify({'error': 'ARL cookie must be alphanumeric.'}), 400

    config = DeezerConfig(cookie_arl=arl_cookie_trimmed)
    client = DeezerClient(config)
    client.initialize()

    task_id = str(uuid.uuid4())
    task_progress_trackers[task_id] = client.progress_tracker

    url_match = re.match(r'https?://(?:www\.)?deezer\.com/(?:\w+/)?(\w+)/(\d+)', url)
    if not url_match:
        if task_id in task_progress_trackers: del task_progress_trackers[task_id] 
        return jsonify({'error': 'Invalid Deezer URL'}), 400

    content_type, content_id = url_match.groups()

    try:
        if content_type == 'track':
            client.download_track(content_id)
        elif content_type == 'album':
            client.download_album(content_id)
        elif content_type == 'playlist':
            client.download_playlist(content_id)
        else:
            if task_id in task_progress_trackers: del task_progress_trackers[task_id] 
            return jsonify({'error': f'Unsupported content type: {content_type}'}), 400
    except DeezerException as e:
        if task_id in task_progress_trackers: del task_progress_trackers[task_id] 
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        if task_id in task_progress_trackers: del task_progress_trackers[task_id]
        app.logger.error(f"Unexpected error during download setup for task {task_id}: {str(e)}")
        return jsonify({'error': 'An unexpected server error occurred.'}), 500

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
