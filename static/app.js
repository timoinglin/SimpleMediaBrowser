// SimpleMediaBrowser client — theme toggle, upload progress, delete confirm, media modal.
(function () {
  // Theme toggle
  const themeBtn = document.getElementById('theme-toggle');
  if (themeBtn) {
    themeBtn.addEventListener('click', function () {
      const cur = document.documentElement.getAttribute('data-theme') || 'light';
      const next = cur === 'dark' ? 'light' : 'dark';
      document.documentElement.setAttribute('data-theme', next);
      localStorage.setItem('mb-theme', next);
    });
  }

  // Upload with progress
  const uploadInput = document.getElementById('upload-input');
  const uploadForm = document.getElementById('upload-form');
  const uploadStatus = document.getElementById('upload-status');
  if (uploadInput && uploadForm) {
    uploadInput.addEventListener('change', function () {
      if (!uploadInput.files || !uploadInput.files.length) return;
      const fd = new FormData(uploadForm);
      const xhr = new XMLHttpRequest();
      xhr.open('POST', uploadForm.action);
      xhr.upload.onprogress = function (e) {
        if (!e.lengthComputable) return;
        const pct = Math.round((e.loaded / e.total) * 100);
        if (uploadStatus) uploadStatus.textContent = 'Uploading… ' + pct + '%';
      };
      xhr.onload = function () {
        if (xhr.status >= 200 && xhr.status < 400) {
          if (uploadStatus) uploadStatus.textContent = 'Done';
          window.location.reload();
        } else {
          if (uploadStatus) uploadStatus.textContent = 'Upload failed (' + xhr.status + ')';
        }
      };
      xhr.onerror = function () {
        if (uploadStatus) uploadStatus.textContent = 'Upload error';
      };
      if (uploadStatus) uploadStatus.textContent = 'Uploading…';
      xhr.send(fd);
    });
  }

  // Delete confirmation
  document.querySelectorAll('.js-confirm-delete').forEach(function (form) {
    form.addEventListener('submit', function (e) {
      const name = form.dataset.name || 'this item';
      if (!confirm('Delete "' + name + '"? This cannot be undone.')) {
        e.preventDefault();
      }
    });
  });

  // Media modal
  const modal = document.getElementById('media-modal');
  const stage = document.getElementById('modal-stage');
  const caption = document.getElementById('modal-caption');
  const closeBtn = document.getElementById('modal-close');

  function openModal(kind, src, title) {
    if (!modal || !stage) return;
    stage.innerHTML = '';
    let el;
    if (kind === 'image') {
      el = document.createElement('img');
      el.src = src;
      el.alt = title || '';
    } else if (kind === 'video') {
      el = document.createElement('video');
      el.src = src;
      el.controls = true;
      el.autoplay = true;
      el.playsInline = true;
    } else if (kind === 'audio') {
      el = document.createElement('audio');
      el.src = src;
      el.controls = true;
      el.autoplay = true;
    } else {
      return;
    }
    stage.appendChild(el);
    if (caption) caption.textContent = title || '';
    modal.hidden = false;
    document.body.style.overflow = 'hidden';
  }

  function closeModal() {
    if (!modal || !stage) return;
    const media = stage.querySelector('video, audio');
    if (media) {
      try { media.pause(); } catch (e) {}
    }
    stage.innerHTML = '';
    if (caption) caption.textContent = '';
    modal.hidden = true;
    document.body.style.overflow = '';
  }

  document.querySelectorAll('.js-open-media').forEach(function (link) {
    link.addEventListener('click', function (e) {
      e.preventDefault();
      openModal(link.dataset.kind, link.href, link.dataset.title || '');
    });
  });

  if (closeBtn) closeBtn.addEventListener('click', closeModal);
  if (modal) {
    modal.addEventListener('click', function (e) {
      if (e.target === modal) closeModal();
    });
  }
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && modal && !modal.hidden) closeModal();
  });
})();
