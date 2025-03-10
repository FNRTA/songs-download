from flask import Flask, request, render_template_string, jsonify
from deezer_downloader.client import DeezerClient  # Import the global variable
from deezer_downloader.config import DeezerConfig
from deezer_downloader.exceptions import DeezerException
from progress_tracker import ProgressTracker
import re

app = Flask(__name__)

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
    </style>
    <script>
      function startDownload() {
        const button = document.querySelector('.button');
        const progress = document.querySelector('.progress');
        const finished = document.querySelector('.finished');
        const form = document.querySelector('form');

        button.disabled = true;
        progress.style.display = 'block';
        finished.style.display = 'none';

        const formData = new FormData(form);
        
          const interval = setInterval(() => {
            fetch('/progress')
              .then(response => response.json())
              .then(data => {
                if (data.finished) {
                  clearInterval(interval);
                  button.disabled = false;
                  progress.style.display = 'none';
                  finished.style.display = 'block';
                  finished.textContent = 'Download finished!';
                } else {
                  progress.textContent = `Downloading ${data.current}/${data.total}`;
                }
              });
          }, 2000);

        fetch('/download', {
          method: 'POST',
          body: formData
        })
        .then(response => response.json())
        .then(data => {
          if (data.error) {
            alert(data.error);
            button.disabled = false;
            progress.style.display = 'none';
            return;
          }


        });
      }
    </script>
  </head>
  <body>
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

# Global variables to track progress
download_progress = {
    'current': 0,
    'total': 0,
    'finished': False
}


@app.route('/', methods=['GET'])
def index():
    return render_template_string(template)


@app.route('/download', methods=['POST'])
def download():
    arl_cookie = request.form['arl_cookie']
    url = request.form['url']

    # Configure client
    config = DeezerConfig(
        cookie_arl=arl_cookie
    )

    client = DeezerClient(config)
    client.initialize()

    # Extract type and ID from URL
    url_match = re.match(r'https?://(?:www\.)?deezer\.com/(?:\w+/)?(\w+)/(\d+)', url)
    if not url_match:
        return jsonify({'error': 'Invalid Deezer URL'})

    content_type, content_id = url_match.groups()

    try:
        if content_type == 'track':
            client.download_track(content_id)
        elif content_type == 'album':
            client.download_album(content_id)
        elif content_type == 'playlist':
            client.download_playlist(content_id)
        else:
            return jsonify({'error': f'Unsupported content type: {content_type}'})
    except DeezerException as e:
        return jsonify({'error': str(e)})

    return jsonify({'success': True})


@app.route('/progress', methods=['GET'])
def progress():
    progress_tracker = ProgressTracker()  # Access the Singleton
    return jsonify(progress_tracker.get_progress())


if __name__ == '__main__':
    app.run(debug=False)
