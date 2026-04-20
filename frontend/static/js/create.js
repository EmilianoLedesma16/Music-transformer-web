Auth.requireAuth();

document.getElementById("logoutBtn").addEventListener("click", Auth.logout);

// Sliders
const tempSlider = document.getElementById("temperature");
const topPSlider = document.getElementById("topP");
tempSlider.addEventListener("input", () => document.getElementById("tempVal").textContent = tempSlider.value);
topPSlider.addEventListener("input", () => document.getElementById("topPVal").textContent = topPSlider.value);

// File input / drop zone
const dropZone  = document.getElementById("dropZone");
const fileInput = document.getElementById("audioInput");
const fileLabel = document.getElementById("fileName");

document.getElementById("browseBtn").addEventListener("click", () => fileInput.click());

fileInput.addEventListener("change", () => {
  if (fileInput.files[0]) showFile(fileInput.files[0]);
});

dropZone.addEventListener("dragover",  e => { e.preventDefault(); dropZone.classList.add("drag-over"); });
dropZone.addEventListener("dragleave", () => dropZone.classList.remove("drag-over"));
dropZone.addEventListener("drop", e => {
  e.preventDefault();
  dropZone.classList.remove("drag-over");
  const file = e.dataTransfer.files[0];
  if (file) { fileInput.files = e.dataTransfer.files; showFile(file); }
});

function showFile(file) {
  fileLabel.textContent = `${file.name} (${(file.size / 1024 / 1024).toFixed(2)} MB)`;
  fileLabel.classList.remove("d-none");
}

function showAlert(msg) {
  const box = document.getElementById("alertBox");
  box.className = "alert alert-danger";
  box.textContent = msg;
}

// Step tracker
const STEP_ORDER = ["VALIDATING","TRANSCRIBING","GENERATING","COMPLETED","FAILED"];
const STEP_IDS   = {
  VALIDATING:   "step-validating",
  TRANSCRIBING: "step-transcribing",
  GENERATING:   "step-generating",
  COMPLETED:    "step-completed",
};

function updateSteps(status) {
  const idx = STEP_ORDER.indexOf(status);
  Object.entries(STEP_IDS).forEach(([s, id]) => {
    const el    = document.getElementById(id);
    const sIdx  = STEP_ORDER.indexOf(s);
    el.classList.remove("active","done");
    if (sIdx < idx)       el.classList.add("done");
    else if (sIdx === idx) el.classList.add("active");
  });
  document.getElementById("statusMsg").textContent =
    status === "FAILED" ? "" :
    status === "COMPLETED" ? "¡Listo! Descarga tus archivos." :
    "Este proceso puede tardar unos minutos…";
}

// Submit
document.getElementById("createForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  if (!fileInput.files[0]) { showAlert("Selecciona un archivo de audio."); return; }

  const btn = document.getElementById("submitBtn");
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Enviando…';

  const fd = new FormData();
  fd.append("audio",       fileInput.files[0]);
  fd.append("genre",       document.getElementById("genre").value);
  fd.append("mood",        document.getElementById("mood").value);
  fd.append("instrument",  document.getElementById("instrument").value);
  fd.append("temperature", tempSlider.value);
  fd.append("top_p",       topPSlider.value);

  try {
    const job = await API.submitProcess(fd);
    document.getElementById("formPanel").style.display  = "none";
    document.getElementById("statusPanel").style.display = "block";
    updateSteps(job.status);
    startPolling(job.id);
  } catch (err) {
    showAlert(err.message);
    btn.disabled = false;
    btn.innerHTML = '<i class="bi bi-magic me-2"></i>Generar acompañamiento';
  }
});

function startPolling(jobId) {
  const interval = setInterval(async () => {
    try {
      const job = await API.pollJob(jobId);
      updateSteps(job.status);

      if (job.status === "COMPLETED") {
        clearInterval(interval);
        showResults(job);
      } else if (job.status === "FAILED") {
        clearInterval(interval);
        document.getElementById("errorPanel").classList.remove("d-none");
        document.getElementById("errorMsg").textContent = job.error_message || "Error desconocido.";
      }
    } catch { /* network hiccup, keep polling */ }
  }, 4000);
}

function showResults(job) {
  const panel = document.getElementById("resultLinks");
  panel.classList.remove("d-none");

  const midiLink = document.getElementById("midiLink");
  const xmlLink  = document.getElementById("xmlLink");

  if (job.midi_output_url) { midiLink.href = job.midi_output_url; midiLink.classList.remove("d-none"); }
  if (job.xml_output_url)  { xmlLink.href  = job.xml_output_url;  xmlLink.classList.remove("d-none"); }
}
