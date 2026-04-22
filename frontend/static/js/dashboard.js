Auth.requireAuth();

const deleteModal    = new bootstrap.Modal(document.getElementById("deleteModal"));
let pendingDeleteId  = null;
let pollingIntervals = {};

document.getElementById("logoutBtn").addEventListener("click", Auth.logout);
document.getElementById("refreshBtn").addEventListener("click", loadCreaciones);

// Cargar datos del usuario (nombre + rol)
API.getMe().then(user => {
  const greeting = document.getElementById("userGreeting");
  if (user.name) { greeting.textContent = `Hola, ${user.name}`; greeting.classList.remove("d-none"); }
  if (user.role === "admin") document.getElementById("adminBtn").classList.remove("d-none");
}).catch(() => {});

document.getElementById("confirmDeleteBtn").addEventListener("click", async () => {
  if (!pendingDeleteId) return;
  try {
    await API.deleteCreacion(pendingDeleteId);
    deleteModal.hide();
    loadCreaciones();
  } catch (err) {
    alert(err.message);
  }
});

function statusBadge(status) {
  const labels = {
    PENDING:      ["Pendiente",     "badge-pending"],
    VALIDATING:   ["Validando",     "badge-validating"],
    TRANSCRIBING: ["Transcribiendo","badge-transcribing"],
    GENERATING:   ["Generando",     "badge-generating"],
    COMPLETED:    ["Completado",    "badge-completed"],
    FAILED:       ["Error",         "badge-failed"],
  };
  const [label, cls] = labels[status] || [status, "badge-pending"];
  return `<span class="badge badge-status ${cls}">${label}</span>`;
}

function isInProgress(status) {
  return ["PENDING","VALIDATING","TRANSCRIBING","GENERATING"].includes(status);
}

function renderCard(c) {
  const date = new Date(c.created_at).toLocaleString("es-MX", {dateStyle:"medium", timeStyle:"short"});

  const midiBtn = c.midi_output_url
    ? `<a href="${c.midi_output_url}" class="btn btn-glass btn-sm" download><i class="bi bi-file-music me-1"></i>MIDI</a>`
    : `<button class="btn btn-glass btn-sm" disabled><i class="bi bi-file-music me-1"></i>MIDI</button>`;

  const xmlBtn = c.xml_output_url
    ? `<a href="${c.xml_output_url}" class="btn btn-glass btn-sm" download><i class="bi bi-file-earmark-code me-1"></i>XML</a>`
    : `<button class="btn btn-glass btn-sm" disabled><i class="bi bi-file-earmark-code me-1"></i>XML</button>`;

  const spinner = isInProgress(c.status)
    ? `<span class="spinner-wood ms-2"></span>`
    : "";

  const detected = c.detected_instrument
    ? `<span class="text-soft small">Detectado: <span class="text-amber">${c.detected_instrument}</span></span>`
    : "";

  const errorLine = c.error_message
    ? `<p class="text-danger small mt-1 mb-0"><i class="bi bi-exclamation-circle me-1"></i>${c.error_message}</p>`
    : "";

  return `
  <div class="col-12 col-md-6 col-xl-4" id="card-${c.id}">
    <div class="creacion-card p-3 h-100 d-flex flex-column gap-2">
      <div class="d-flex justify-content-between align-items-start">
        <div>
          ${statusBadge(c.status)} ${spinner}
          <p class="text-white fw-semibold mb-0 mt-1">${c.original_filename || `Creación #${c.id}`}</p>
        </div>
        <button class="btn btn-sm btn-glass ms-2 flex-shrink-0 delete-btn" data-id="${c.id}">
          <i class="bi bi-trash3"></i>
        </button>
      </div>

      <div class="d-flex flex-wrap gap-2 small text-soft">
        <span><i class="bi bi-music-note me-1"></i>${c.genre}</span>
        <span><i class="bi bi-emoji-smile me-1"></i>${c.mood}</span>
        <span><i class="bi bi-guitar me-1"></i>${c.instrument}</span>
      </div>

      ${detected}
      ${errorLine}

      <p class="text-soft small mb-0 mt-auto"><i class="bi bi-clock me-1"></i>${date}</p>

      <div class="d-flex gap-2 mt-1">
        ${midiBtn}
        ${xmlBtn}
      </div>
    </div>
  </div>`;
}

function pollCard(id) {
  if (pollingIntervals[id]) return;
  pollingIntervals[id] = setInterval(async () => {
    try {
      const c = await API.pollJob(id);
      const container = document.getElementById(`card-${id}`);
      if (container) container.outerHTML = renderCard(c);
      attachDeleteListeners();
      if (!isInProgress(c.status)) {
        clearInterval(pollingIntervals[id]);
        delete pollingIntervals[id];
      }
    } catch { /* ignore */ }
  }, 4000);
}

function attachDeleteListeners() {
  document.querySelectorAll(".delete-btn").forEach(btn => {
    btn.onclick = () => {
      pendingDeleteId = parseInt(btn.dataset.id, 10);
      deleteModal.show();
    };
  });
}

async function loadCreaciones() {
  Object.values(pollingIntervals).forEach(clearInterval);
  pollingIntervals = {};

  document.getElementById("loadingState").classList.remove("d-none");
  document.getElementById("emptyState").classList.add("d-none");
  document.getElementById("creacionesGrid").classList.add("d-none");

  try {
    const list = await API.listCreaciones();
    document.getElementById("loadingState").classList.add("d-none");

    if (list.length === 0) {
      document.getElementById("emptyState").classList.remove("d-none");
      return;
    }

    const grid = document.getElementById("creacionesGrid");
    grid.innerHTML = list.map(renderCard).join("");
    grid.classList.remove("d-none");
    attachDeleteListeners();

    list.filter(c => isInProgress(c.status)).forEach(c => pollCard(c.id));
  } catch (err) {
    document.getElementById("loadingState").innerHTML =
      `<p class="text-danger"><i class="bi bi-exclamation-circle me-1"></i>${err.message}</p>`;
  }
}

loadCreaciones();
