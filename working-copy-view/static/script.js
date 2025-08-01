document.addEventListener('DOMContentLoaded', () => {

  // Checkbox "selectAll" obsługa
  const selectAllCheckbox = document.getElementById('selectAll');
  if (selectAllCheckbox) {
    selectAllCheckbox.onclick = function() {
      let ch = this.checked;
      document.querySelectorAll('input[name="file"]').forEach(c => c.checked = ch);
    };
  }
  });

  function showToast(message, type = 'primary') {
  const existing = document.querySelector('.toast');
  if (existing) {
    existing.remove();
  }

  const toast = document.createElement('div');
  toast.className = `toast ${type} show`;
  toast.textContent = message;

  document.body.appendChild(toast);

  setTimeout(() => {
    toast.classList.remove('show');
    setTimeout(() => toast.remove(), 300);
  }, 3000);
}

  // Obsługa pokazania toast po reloadzie (localStorage)
  const toastDataRaw = localStorage.getItem('showToast');
  if (toastDataRaw) {
    const { message, type } = JSON.parse(toastDataRaw);
    localStorage.removeItem('showToast');
    showToast(message, type);
  }

  // Modal Bulma
  const imageModal = document.getElementById('imageModal');
  const modalImage = document.getElementById('modalImage');
  const modalCloseButtons = imageModal.querySelectorAll('.modal-background, .modal-close');

  // Zamknięcie modala po kliknięciu na tło lub przycisk zamknięcia lub obrazek
  modalCloseButtons.forEach(btn => btn.addEventListener('click', hideImageModal));
  modalImage.addEventListener('click', hideImageModal);

  // Funkcja pokazująca modal z powiększonym obrazem
  window.showImageModal = function(src) {
    modalImage.src = src;
    imageModal.classList.add('is-active');
  };

  function hideImageModal() {
    imageModal.classList.remove('is-active');
    modalImage.src = "";
  }



// Formatowanie rozmiaru pliku w czytelnej formie
function formatSize(bytes) {
  if (bytes < 1024) return bytes + " B";
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
  return (bytes / (1024 * 1024)).toFixed(1) + " MB";
}

// Render podglądu pliku (zrobione raczej po stronie Jinja2, ale zostawiam na wszelki wypadek)
function renderPreview(file) {
  if (file.type === 'image')
    return `<img src="/files/${encodeURIComponent(file.name)}" class="preview" style="cursor:pointer;" onclick="showImageModal(this.src)">`;
  if (file.type === 'video')
    return `<video src="/files/${encodeURIComponent(file.name)}" class="preview" controls></video>`;
  return "";
}

// Przenoszenie pojedynczego pliku
function moveSelectedSingle(file, dest) {
  fetch('/api/move', {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({ dest: dest, files: [file] })
  }).then(r => r.json()).then(resp => {
    localStorage.setItem('showToast', JSON.stringify({ message: 'Przeniesiono: ' + file, type: 'success' }));
    window.location.reload();
  }).catch(() => {
    showToast('Błąd podczas przenoszenia pliku!', 'danger');
  });
}

// Przenoszenie zaznaczonych plików
function moveSelected(dest) {
  let checked = Array.from(document.querySelectorAll('input[name="file"]:checked')).map(x => x.value);
  if (checked.length === 0) {
    showToast('Nie zaznaczono plików!', 'warning');
    return;
  }
  fetch('/api/move', {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({ dest: dest, files: checked })
  }).then(r => r.json()).then(resp => {
    localStorage.setItem('showToast', JSON.stringify({ message: 'Przeniesiono: ' + (resp.moved || []).join(", "), type: 'success' }));
    window.location.reload();
  }).catch(() => {
    showToast('Błąd podczas przenoszenia plików!', 'danger');
  });
}
