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
              progress.style.display = 'none';
              finished.textContent = 'Download finished!';
              finished.style.display = 'block';
              clearInterval(currentInterval);
              currentInterval = null;
              button.disabled = false;
              currentTaskId = null;
            } else if (progressData.hasOwnProperty('current') &&
            progressData.hasOwnProperty('total')) {
              progress.textContent = `Downloading: ${progressData.current}/${progressData.total}`;
            }
          })
          .catch(error => {
            console.error('Error fetching progress:', error);
            showSnackbar('Error fetching progress. Please try again.');
            clearInterval(currentInterval);
            currentInterval = null;
            button.disabled = false;
            progress.style.display = 'none';
            currentTaskId = null;
          });
      }, 2000);
    } else {
        showSnackbar(data.message || 'Task ID not received.');
        button.disabled = false;
        progress.style.display = 'none';
    }
  })
  .catch(error => {
    console.error('Error starting download:', error);
    showSnackbar('Error starting download. Please check console and try again.');
    button.disabled = false;
    progress.style.display = 'none';
  });
}

function showSnackbar(message) {
  const snackbar = document.getElementById("snackbar");
  snackbar.textContent = message;
  snackbar.className = "show";
  setTimeout(function(){ snackbar.className = snackbar.className.replace("show", ""); }, 3000);
}
