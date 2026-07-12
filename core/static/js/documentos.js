document.addEventListener('DOMContentLoaded', function () {
    const fileInput = document.getElementById('id_archivo');
    const trigger = document.getElementById('upload-trigger');
    const preview = document.getElementById('file-preview');
    const previewName = document.getElementById('file-preview-name');
    const previewSize = document.getElementById('file-preview-size');
    const removeBtn = document.getElementById('file-preview-remove');
    const form = document.getElementById('upload-form');
    const overlay = document.getElementById('loading-overlay');
    const submitBtn = document.getElementById('upload-submit');

    if (!fileInput || !form) {
        return;
    }

    function humanFileSize(bytes) {
        if (bytes < 1024) {
            return bytes + ' B';
        }
        const units = ['KB', 'MB', 'GB'];
        let i = -1;
        do {
            bytes /= 1024;
            i++;
        } while (bytes >= 1024 && i < units.length - 1);
        return bytes.toFixed(1) + ' ' + units[i];
    }

    fileInput.addEventListener('change', function () {
        if (fileInput.files && fileInput.files.length > 0) {
            const file = fileInput.files[0];
            previewName.textContent = file.name;
            previewSize.textContent = humanFileSize(file.size);
            preview.hidden = false;
            trigger.classList.add('has-file');
        } else {
            preview.hidden = true;
            trigger.classList.remove('has-file');
        }
    });

    removeBtn.addEventListener('click', function () {
        fileInput.value = '';
        preview.hidden = true;
        trigger.classList.remove('has-file');
    });

    form.addEventListener('submit', function () {
        overlay.classList.add('active');
        submitBtn.disabled = true;
    });
});
