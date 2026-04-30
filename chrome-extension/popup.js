document.addEventListener('DOMContentLoaded', () => {
  const setupDiv = document.getElementById('setup');
  const appFrame = document.getElementById('appFrame');
  const serverUrlInput = document.getElementById('serverUrl');
  const saveBtn = document.getElementById('saveBtn');

  // Load saved URL if it exists
  chrome.storage.sync.get(['renderUrl'], (result) => {
    if (result.renderUrl) {
      setupDiv.style.display = 'none';
      appFrame.src = result.renderUrl;
    }
  });

  saveBtn.addEventListener('click', () => {
    let url = serverUrlInput.value.trim();
    if (!url) return;
    
    // Auto-append /interview if they just put the base URL
    if (!url.endsWith('/interview')) {
      url = url.replace(/\/$/, '') + '/interview';
    }

    chrome.storage.sync.set({ renderUrl: url }, () => {
      setupDiv.style.display = 'none';
      appFrame.src = url;
    });
  });
});
