// common.js - Shared utilities for all pages

// Show a toast notification
function showToast(message, type = '') {
    const toast = document.getElementById('toast');
    if (!toast) return;
    toast.textContent = message;
    toast.className = 'toast show ' + type;
    setTimeout(() => toast.classList.remove('show'), 2800);
}

// Simulate a progress bar (replace with real progress callbacks later)
function simulateProgress(containerId, callback) {
    const container = document.getElementById(containerId);
    if (!container) return;
    const fill = container.querySelector('.progress-fill');
    container.style.display = 'block';
    let width = 0;
    const interval = setInterval(() => {
        width += Math.random() * 15 + 5;
        if (width >= 100) {
            width = 100;
            clearInterval(interval);
            fill.style.width = '100%';
            setTimeout(() => {
                container.style.display = 'none';
                if (callback) callback();
            }, 500);
        } else {
            fill.style.width = `${Math.min(width, 100)}%`;
        }
    }, 150);
}

// Setup drag & drop for a file input area
function setupDragAndDrop(uploadAreaId, fileInputId, onFileSelected) {
    const uploadArea = document.getElementById(uploadAreaId);
    const fileInput = document.getElementById(fileInputId);

    if (!uploadArea || !fileInput) return;

    uploadArea.addEventListener('click', () => fileInput.click());
    uploadArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadArea.classList.add('drag-over');
    });
    uploadArea.addEventListener('dragleave', () => {
        uploadArea.classList.remove('drag-over');
    });
    uploadArea.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadArea.classList.remove('drag-over');
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            fileInput.files = files;
            if (onFileSelected) onFileSelected(files[0]);
        }
    });

    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0 && onFileSelected) {
            onFileSelected(e.target.files[0]);
        }
    });
}