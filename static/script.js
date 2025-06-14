document.addEventListener('DOMContentLoaded', (event) => {
  const storedArlCookie = localStorage.getItem('arlCookieValue');
  if (storedArlCookie) {
    document.getElementById('arl_cookie').value = storedArlCookie;
  }
});

let currentInterval = null;
let currentTaskId = null;

function startDownload() {
  const url = document.getElementById('url').value;
  const arlCookie = document.getElementById('arl_cookie').value;
  const progressDiv = document.querySelector('.progress');
  const finishedDiv = document.querySelector('.finished');
  const downloadReadyDiv = document.querySelector('.download-ready');
  
  // Save ARL cookie to localStorage
  if (arlCookie) {
    localStorage.setItem('arlCookieValue', arlCookie);
  }


  // Reset UI
  progressDiv.style.display = 'none';
  finishedDiv.style.display = 'none';
  downloadReadyDiv.style.display = 'none';

  if (!url || !arlCookie) {
    showSnackbar('URL and ARL cookie are required.');
    return;
  }

  progressDiv.style.display = 'block';

  const formData = new FormData();
  formData.append('url', url);
  formData.append('arl_cookie', arlCookie);

  fetch('/download', {
    method: 'POST',
    body: formData
  })
  .then(response => response.json())
  .then(data => {
    if (data.error) {
      showSnackbar(`Error: ${data.error}`);
      progressDiv.style.display = 'none';
    } else if (data.success && data.task_id) {
      pollProgress(data.task_id);
    } else {
      showSnackbar('An unknown error occurred.');
      progressDiv.style.display = 'none';
    }
  })
  .catch(error => {
    showSnackbar(`Request failed: ${error}`);
    progressDiv.style.display = 'none';
  });
}

function pollProgress(taskId) {
  const progressDiv = document.querySelector('.progress');
  const finishedDiv = document.querySelector('.finished');
  const downloadReadyDiv = document.querySelector('.download-ready');
  const downloadButton = document.querySelector('.download-button');

  const interval = setInterval(() => {
    fetch(`/progress?task_id=${taskId}`)
      .then(response => response.json())
      .then(data => {
        if (data.error && data.finished) {
          showSnackbar(data.error);
          progressDiv.style.display = 'none';
          clearInterval(interval);
          return;
        }

        if (data.finished) {
          progressDiv.style.display = 'none';
          clearInterval(interval);

          if (data.zip_ready) {
            // Zip is ready, show download button
            finishedDiv.style.display = 'none';
            downloadReadyDiv.style.display = 'block';
            downloadButton.onclick = () => {
              window.open(`/download_zip/${taskId}`, '_blank');
            };
          } else if (data.error) {
            // Handle case where it finished with an error but no zip
            showSnackbar(`Error: ${data.error}`);
          } else {
            // Finished successfully but no zip (should not happen with new flow)
            finishedDiv.style.display = 'block';
          }
        } else if (!data.starting) {
          progressDiv.textContent = `Downloading... ${data.current} / ${data.total}`;
        }
      })
      .catch(error => {
        showSnackbar(`Polling failed: ${error}`);
        progressDiv.style.display = 'none';
        clearInterval(interval);
      });
  }, 2000);
}

function showSnackbar(message) {
  const snackbar = document.getElementById('snackbar');
  snackbar.textContent = message;
  snackbar.className = 'show';
  setTimeout(() => { snackbar.className = snackbar.className.replace('show', ''); }, 3000);
}
