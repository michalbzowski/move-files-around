document.getElementById('selectAll').onclick = function() {
  let ch = this.checked;
  document.querySelectorAll('input[name="file"]').forEach(c => c.checked = ch);
};

window.addEventListener('DOMContentLoaded', () => {
  const toastDataRaw = localStorage.getItem('showToast');
  if (toastDataRaw) {
    const {message, type} = JSON.parse(toastDataRaw);
    localStorage.removeItem('showToast');
    showToast(message, type);
  }
});

const toastLiveExample = document.getElementById('liveToast');
const toastBody = document.getElementById('toastBody');
const bsToast = new bootstrap.Toast(toastLiveExample);
const imageModal = document.getElementById('imageModal');
console.log(imageModal);  // powinno wypisać element, a nie null
const modalImage = document.getElementById('modalImage');

function renderPreview(file) {
  if (file.type === 'image')
    return `<img src="/files/${encodeURIComponent(file.name)}" class="preview" style="cursor:pointer;" onclick="showImageModal(this.src)">`;
  if (file.type === 'video')
    return `<video src="/files/${encodeURIComponent(file.name)}" class="preview" controls></video>`;
  return "";
}

function showToast(message, type = 'primary') {
  // Zmień kolor tła według typu ('primary', 'success', 'danger', 'warning', 'info')
  toastLiveExample.className = `toast align-items-center text-white bg-${type} border-0`;
  toastBody.textContent = message;
  bsToast.show();
}

function formatSize(bytes) {
  if(bytes < 1024) return bytes + " B";
  if(bytes < 1024*1024) return (bytes/1024).toFixed(1) + " KB";
  return (bytes/(1024*1024)).toFixed(1) + " MB";
}

function moveSelectedSingle(file, dest) {
  fetch('/api/move', {
    method: "POST",
    headers: {"Content-Type":"application/json"},
    body: JSON.stringify({ dest: dest, files: [file] })
  }).then(r=>r.json()).then(resp=>{
    localStorage.setItem('showToast', JSON.stringify({ message: 'Przeniesiono: ' + file, type: 'success' }));
    window.location.reload()
  });

}

function showImageModal(src) {
  modalImage.src = src;
  imageModal.classList.add('show');
}

function hideImageModal() {
  imageModal.classList.remove('show');
  modalImage.src = "";
}

imageModal.onclick = function(e) {
  if (e.target === imageModal || e.target === modalImage) {
    hideImageModal();
  }
}

function moveSelected(dest) {
  let checked = Array.from(document.querySelectorAll('input[name="file"]:checked')).map(x=>x.value);
  if(checked.length===0) { showToast('Nie zaznaczono plików!', 'warning'); return; }
  fetch('/api/move', {
    method: "POST",
    headers: {"Content-Type":"application/json"},
    body: JSON.stringify({dest: dest, files: checked})
  }).then(r=>r.json()).then(resp=>{
    localStorage.setItem('showToast', JSON.stringify({ message: 'Przeniesiono: ' + (resp.moved||[]).join(", "), type: 'success' }));
    window.location.reload()
  });
}