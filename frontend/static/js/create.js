/**
 * Create page — upload de audio, envío del form y polling de estado.
 * Requiere: auth.js, api.js
 */
Auth.requireAuth();

const STEPS = ['VALIDATING', 'TRANSCRIBING', 'GENERATING', 'COMPLETED'];

// ── Drop zone ─────────────────────────────────────────────────────────────────
const dropZone  = document.getElementById('dropZone');
const audioInput = document.getElementById('audioInput');
const fileInfo   = document.getElementById('fileInfo');

dropZone.addEventListener('click', () => audioInput.click());

dropZone.addEventListener('dragover', e => {
  e.preventDefault();
  dropZone.classList.add('dragover');
});
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));
dropZone.addEventListener('drop', e => {
  e.preventDefault();
  dropZone.classList.remove('dragover');
  const file = e.dataTransfer.files[0];
  if (file) setFile(file);
});

audioInput.addEventListener('change', () => {
  if (audioInput.files[0]) setFile(audioInput.files[0]);
});

function setFile(file) {
  // Transferir al input para que FormData lo recoja
  const dt = new DataTransfer();
  dt.items.add(file);
  audioInput.files = dt.files;

  fileInfo.textContent = `${file.name} (${(file.size / 1024 / 1024).toFixed(1)} MB)`;
  fileInfo.classList.remove('d-none');
}

// ── Envío del formulario ──────────────────────────────────────────────────────
document.getElementById('createForm').addEventListener('submit', async e => {
  e.preventDefault();

  const submitBtn = document.getElementById('submitBtn');
  submitBtn.disabled = true;
  submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Enviando…';

  const formData = new FormData(e.target);

  const res = await API.process(formData);

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    submitBtn.disabled = false;
    submitBtn.innerHTML = '<i class="bi bi-magic me-2"></i>Generar acompañamiento';
    alert(err.detail || 'Error al enviar el audio');
    return;
  }

  const job = await res.json();

  // Ocultar el form, mostrar progreso
  document.getElementById('createForm').classList.add('d-none');
  document.getElementById('progressPanel').classList.remove('d-none');

  startPolling(job.id, job.status);
});

// ── Polling de estado ─────────────────────────────────────────────────────────
function setStepState(status) {
  STEPS.forEach(step => {
    const el = document.getElementById(`step-${step}`);
    if (!el) return;
    el.classList.remove('active', 'done', 'error');
  });

  const currentIdx = STEPS.indexOf(status);

  STEPS.forEach((step, i) => {
    const el = document.getElementById(`step-${step}`);
    if (!el) return;
    if (status === 'FAILED') {
      if (i < currentIdx) el.classList.add('done');
    } else {
      if (i < currentIdx) el.classList.add('done');
      else if (i === currentIdx) el.classList.add('active');
    }
  });
}

async function startPolling(jobId, initialStatus) {
  setStepState(initialStatus);

  const poll = async () => {
    const res = await API.getJob(jobId);
    if (!res.ok) {
      setTimeout(poll, 4000);
      return;
    }
    const job = await res.json();
    setStepState(job.status);

    if (job.status === 'COMPLETED') {
      onCompleted(job);
    } else if (job.status === 'FAILED') {
      onFailed(job);
    } else {
      setTimeout(poll, 3000);
    }
  };

  setTimeout(poll, 2000);
}

function onCompleted(job) {
  document.getElementById('step-COMPLETED').classList.remove('active');
  document.getElementById('step-COMPLETED').classList.add('done');
  document.getElementById('resultBlock').classList.remove('d-none');

  const midiLink = document.getElementById('midiDownload');
  const xmlLink  = document.getElementById('xmlDownload');

  if (job.midi_output_url) midiLink.href = job.midi_output_url;
  else midiLink.classList.add('d-none');

  if (job.xml_output_url) xmlLink.href = job.xml_output_url;
  else xmlLink.classList.add('d-none');

  if (job.notes_generated != null) {
    document.getElementById('resultStats').textContent =
      `${job.notes_generated} notas generadas · ${(job.duration_seconds || 0).toFixed(1)} segundos`;
  }
}

function onFailed(job) {
  STEPS.forEach(s => {
    const el = document.getElementById(`step-${s}`);
    if (el && el.classList.contains('active')) el.classList.add('error');
  });
  document.getElementById('errorBlock').classList.remove('d-none');
  document.getElementById('errorMsg').textContent =
    job.error_message || 'Ocurrió un error inesperado.';
}
