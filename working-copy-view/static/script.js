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

  document.addEventListener('DOMContentLoaded', () => {
  const filterExtSelect = document.getElementById('filterExt');
  if (filterExtSelect) {
    new Choices(filterExtSelect, {
      removeItemButton: true,
      maxItemCount: -1,
      searchEnabled: true,
      shouldSort: true,
      placeholder: true,
      placeholderValue: 'Rozszerzenia'
    });
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

document.addEventListener('DOMContentLoaded', () => {
  // PDF modal
  const pdfModal = document.getElementById('pdfModal');
  const pdfObject = document.getElementById('pdfObject');
  const pdfModalClose = pdfModal.querySelector('.modal-close, .modal-background');

  pdfModalClose.addEventListener('click', () => {
    pdfModal.classList.remove('is-active');
    pdfObject.data = '';
  });

  window.showPdfModal = function(src) {
    pdfObject.data = src;
    pdfModal.classList.add('is-active');
  };

  // Text modal
  const textModal = document.getElementById('textModal');
  const textContent = document.getElementById('textContent');
  const textModalClose = textModal.querySelector('.modal-close, .modal-background');

  textModalClose.addEventListener('click', () => {
    textModal.classList.remove('is-active');
    textContent.textContent = '';
  });

  window.showTextModal = function(url) {
    fetch(url)
      .then(res => {
        if(!res.ok) throw new Error('Błąd ładowania pliku');
        return res.text();
      })
      .then(text => {
        textContent.textContent = text;
        textModal.classList.add('is-active');
      })
      .catch(() => {
        textContent.textContent = '[Nie można wyświetlić podglądu tekstu]';
        textModal.classList.add('is-active');
      });
  };
});

// Inicjalizacja modala Bulma
    document.addEventListener('DOMContentLoaded', () => {
        const modal = document.getElementById('imageModal');
        const modalClose = modal.querySelector('.modal-close');
        const modalBackground = modal.querySelector('.modal-background');
        const modalImage = document.getElementById('modalImage');

        function closeModal() {
            modal.classList.remove('is-active');
            modalImage.src = "";
        }

        modalClose.onclick = closeModal;
        modalBackground.onclick = closeModal;
        modalImage.onclick = closeModal;

        window.showImageModal = function(src) {
            modalImage.src = src;
            modal.classList.add('is-active');
        };

        // Obsługa checkbox "selectAll"
        const selectAllCheckbox = document.getElementById('selectAll');
        selectAllCheckbox.addEventListener('change', function() {
            const checkboxes = document.querySelectorAll('input[name="file"]');
            checkboxes.forEach(ch => ch.checked = this.checked);
        });
    });

document.getElementById('refreshTagsBtn').addEventListener('click', (event) => {
  // (opcjonalnie) pokaż jakiś progress lub status
  event.preventDefault()
  const statusDiv = document.getElementById('refreshStatus');
  statusDiv.innerText = "Uruchamiam odświeżanie tagów...";

  fetch('/classify_images')
    .then(response => response.json())
    .then(data => {
      if(data.status === 'started') {
        statusDiv.innerText = "Odświeżanie tagów w toku, możesz kontynuować pracę.";
        // (opcjonalnie) wywołaj mechanizm odświeżenia listy plików po jakimś czasie
      } else {
        statusDiv.innerText = "Nieoczekiwana odpowiedź z serwera.";
      }
    })
    .catch(err => {
      statusDiv.innerText = "Błąd podczas odświeżania: " + err;
    });
});



//obracanie obrazków

function correctImageOrientation(imgElement) {
  EXIF.getData(imgElement, function() {
    var orientation = EXIF.getTag(this, "Orientation") || 1;
    switch (orientation) {
      case 2:
        // Flip horizontal
        imgElement.style.transform = "scaleX(-1)";
        break;
      case 3:
        // Rotate 180°
        imgElement.style.transform = "rotate(180deg)";
        break;
      case 4:
        // Flip vertical
        imgElement.style.transform = "scaleY(-1)";
        break;
      case 5:
        // Rotate 90° CW and flip horizontal
        imgElement.style.transform = "rotate(90deg) scaleX(-1)";
        break;
      case 6:
        // Rotate 90° CW
        imgElement.style.transform = "rotate(90deg)";
        break;
      case 7:
        // Rotate 90° CCW and flip horizontal
        imgElement.style.transform = "rotate(-90deg) scaleX(-1)";
        break;
      case 8:
        // Rotate 90° CCW
        imgElement.style.transform = "rotate(-90deg)";
        break;
      default:
        // Orientation = 1 means no rotation needed
        imgElement.style.transform = "rotate(90deg)";
        break;
    }
  });
}


