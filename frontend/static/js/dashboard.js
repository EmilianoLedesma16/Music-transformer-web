/**
 * Dashboard — lista y polling de creaciones.
 * Requiere: auth.js, api.js
 */
Auth.requireAuth();

const STATUS_LABELS = {
  PENDING:      { text: 'Pendiente',    cls: 'status-PENDING' },
  VALIDATING:   { text: 'Validando',    cls: 'status-VALIDATING' },
  TRANSCRIBING: { text: 'Transcribiendo', cls: 'status-TRANSCRIBING' },
  GENERATING:   { text: 'Generando',    cls: 'status-GENERATING' },
  COMPLETED:    { text: 'Completado',   cls: 'status-COMPLETED' },
  FAILED:       { text: 'Error',        cls: 'status-FAILED' },
};

const IN_PROGRESS = new Set(['PENDING', 'VALIDATING', 'TRANSCRIBING', 'GENERATING']);

let creaciones = [];
let pollTimer  = null;

async function loadCreaciones() {
  const res = await API.getCreaciones();
  if (res.status === 401) { Auth.logout(); return; }
  if (!res.ok) return;

  creaciones = await res.json();

  const list    = document.getElementById('creacionesList');
  const empty   = document.getElementById('emptyState');
  const spinner = document.getElementById('loadingSpinner');

  spinner.classList.add('d-none');

  if (creaciones.length === 0) {
    empty.classList.remove('d-none');
    return;
  }

  list.innerHTML = '';
  list.classList.remove('d-none');

  creaciones.forEach(c => renderCard(c, list));

  // Polling: refrescar las que estén en proceso
  const inProgress = creaciones.filter(c => IN_PROGRESS.has(c.status));
  if (inProgress.length > 0) {
    clearTimeout(pollTimer);
    pollTimer = setTimeout(pollInProgress, 3000);
  }
}

function renderCard(c, container) {
  const tmpl  = document.getElementById('cardTemplate').content.cloneNode(true);
  const card  = tmpl.querySelector('.col-md-6');
  card.dataset.id = c.id;

  tmpl.querySelector('.filename').textContent      = c.original_filename;
  tmpl.querySelector('.genre-badge').textContent   = c.genre;
  tmpl.querySelector('.mood-badge').textContent    = c.mood;
  tmpl.querySelector('.instrument-badge').textContent = c.instrument;
  tmpl.querySelector('.created-at').textContent    =
    new Date(c.created_at).toLocaleString('es-MX');

  const info = STATUS_LABELS[c.status] || { text: c.status, cls: '' };
  const badge = tmpl.querySelector('.status-badge');
  badge.textContent = info.text;
  badge.classList.add('badge', info.cls);

  if (c.status === 'COMPLETED') {
    const links = tmpl.querySelector('.output-links');
    links.classList.remove('d-none');
    const midiLink = tmpl.querySelector('.midi-link');
    const xmlLink  = tmpl.querySelector('.xml-link');
    if (c.midi_output_url) midiLink.href = c.midi_output_url;
    else midiLink.classList.add('d-none');
    if (c.xml_output_url)  xmlLink.href  = c.xml_output_url;
    else xmlLink.classList.add('d-none');
    if (c.notes_generated != null) {
      tmpl.querySelector('.notes-info').textContent =
        `${c.notes_generated} notas · ${(c.duration_seconds || 0).toFixed(1)}s`;
    }
  }

  if (c.status === 'FAILED') {
    const eb = tmpl.querySelector('.error-block');
    eb.classList.remove('d-none');
    eb.querySelector('.error-msg').textContent = c.error_message || 'Error desconocido';
  }

  tmpl.querySelector('.delete-btn').addEventListener('click', () => deleteCreacion(c.id));

  container.appendChild(tmpl);
}

async function pollInProgress() {
  const list = document.getElementById('creacionesList');
  let stillRunning = false;

  for (const c of creaciones) {
    if (!IN_PROGRESS.has(c.status)) continue;
    const res = await API.getJob(c.id);
    if (!res.ok) continue;
    const updated = await res.json();

    // Actualizar la tarjeta en el DOM
    const existing = list.querySelector(`[data-id="${c.id}"]`);
    if (existing) existing.remove();

    Object.assign(c, updated);
    renderCard(updated, list);

    if (IN_PROGRESS.has(updated.status)) stillRunning = true;
  }

  if (stillRunning) pollTimer = setTimeout(pollInProgress, 3000);
}

async function deleteCreacion(id) {
  if (!confirm('¿Borrar esta creación? Esta acción es permanente.')) return;
  const res = await API.deleteCreacion(id);
  if (res.ok || res.status === 204) {
    creaciones = creaciones.filter(c => c.id !== id);
    const card = document.getElementById('creacionesList')
                         .querySelector(`[data-id="${id}"]`);
    if (card) card.remove();
    if (creaciones.length === 0) {
      document.getElementById('creacionesList').classList.add('d-none');
      document.getElementById('emptyState').classList.remove('d-none');
    }
  }
}

loadCreaciones();
