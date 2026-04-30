Auth.requireAuth();
document.getElementById("logoutBtn").addEventListener("click", Auth.logout);

// ── Wizard state ───────────────────────────────────────────────────────────────
let currentStep = 1;

function setWizardStep(step) {
  currentStep = step;

  // panels
  document.getElementById("panel-step1").style.display = step === 1 ? "block" : "none";
  document.getElementById("panel-step2").style.display = step === 2 ? "block" : "none";
  document.getElementById("statusPanel").style.display = step === 3 ? "block" : "none";

  // indicator dots
  ["wz1","wz2","wz3"].forEach((id, i) => {
    const el = document.getElementById(id);
    el.classList.remove("active","done");
    if (i + 1 < step)      el.classList.add("done");
    else if (i + 1 === step) el.classList.add("active");
  });
}

// ── File drop zone ─────────────────────────────────────────────────────────────
const dropZone  = document.getElementById("dropZone");
const fileInput = document.getElementById("audioInput");
const fileLabel = document.getElementById("fileName");

document.getElementById("browseBtn").addEventListener("click", () => fileInput.click());
fileInput.addEventListener("change", () => { if (fileInput.files[0]) showFile(fileInput.files[0]); });

dropZone.addEventListener("dragover",  e => { e.preventDefault(); dropZone.classList.add("drag-over"); });
dropZone.addEventListener("dragleave", () => dropZone.classList.remove("drag-over"));
dropZone.addEventListener("drop", e => {
  e.preventDefault();
  dropZone.classList.remove("drag-over");
  if (e.dataTransfer.files[0]) { fileInput.files = e.dataTransfer.files; showFile(e.dataTransfer.files[0]); }
});

function showFile(file) {
  fileLabel.textContent = `${file.name}  (${(file.size / 1024 / 1024).toFixed(2)} MB)`;
  fileLabel.classList.remove("d-none");
}

// ── Alert helpers ──────────────────────────────────────────────────────────────
function showAlert(msg, boxId = "alertBox") {
  const box = document.getElementById(boxId);
  box.className = "alert alert-danger mb-3";
  box.textContent = msg;
}
function hideAlert(boxId = "alertBox") {
  document.getElementById(boxId).className = "d-none mb-3";
}

// ── Pill selectors ─────────────────────────────────────────────────────────────
function initPills(groupId) {
  document.querySelectorAll(`#${groupId} .pill-opt`).forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(`#${groupId} .pill-opt`).forEach(b => b.classList.remove("selected"));
      btn.classList.add("selected");
    });
  });
}
initPills("energyPills");
initPills("instrumentPills");

function getPill(groupId) {
  const sel = document.querySelector(`#${groupId} .pill-opt.selected`);
  return sel ? sel.dataset.val : null;
}
function setPill(groupId, val) {
  document.querySelectorAll(`#${groupId} .pill-opt`).forEach(btn => {
    btn.classList.toggle("selected", btn.dataset.val === val);
  });
}

// ── Sliders ────────────────────────────────────────────────────────────────────
const tempSlider = document.getElementById("temperature");
const topPSlider = document.getElementById("topP");
tempSlider.addEventListener("input", () => document.getElementById("tempVal").textContent = tempSlider.value);
topPSlider.addEventListener("input", () => document.getElementById("topPVal").textContent = topPSlider.value);

// ── Step 1 → Step 2 (parse prompt) ────────────────────────────────────────────
document.getElementById("nextBtn").addEventListener("click", async () => {
  hideAlert("alertBox");

  if (!fileInput.files[0]) {
    showAlert("Selecciona un archivo de audio antes de continuar.", "alertBox");
    return;
  }

  const btn  = document.getElementById("nextBtn");
  const orig = btn.innerHTML;
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner-wood me-2"></span>Interpretando…';

  const text = document.getElementById("promptInput").value.trim();

  try {
    if (text) {
      const res = await API.parsePrompt(text);
      applyParsed(res);
    }
    setWizardStep(2);
  } catch (err) {
    // parse-prompt failed → still advance but show notice
    setWizardStep(2);
    showConfidence(0, false);
  } finally {
    btn.disabled = false;
    btn.innerHTML = orig;
  }
});

function applyParsed(res) {
  const detected = res.detected || {};

  // Genre
  if (detected.genre) document.getElementById("genre").value = res.genre;
  setDetectTag("tag-genre", detected.genre);

  // Mood
  if (detected.mood) document.getElementById("mood").value = res.mood;
  setDetectTag("tag-mood", detected.mood);

  // Energy
  if (detected.energy) setPill("energyPills", res.energy);
  setDetectTag("tag-energy", detected.energy);

  // Instrument
  if (detected.instrument) setPill("instrumentPills", res.instrument);
  setDetectTag("tag-instrument", detected.instrument);

  showConfidence(res.confidence, true);
}

function setDetectTag(id, detected) {
  const el = document.getElementById(id);
  if (detected) {
    el.className = "detect-tag yes";
    el.textContent = "detectado";
  } else {
    el.className = "detect-tag no";
    el.textContent = "auto";
  }
}

function showConfidence(conf, fromPrompt) {
  const badge = document.getElementById("confBadge");
  const msg   = document.getElementById("confMsg");

  if (!fromPrompt) {
    badge.className = "conf-badge conf-low";
    badge.innerHTML = '<i class="bi bi-exclamation-circle me-1"></i>Sin prompt';
    msg.textContent = "Ajusta los parámetros manualmente.";
    return;
  }

  const pct = Math.round(conf * 100);
  if (conf >= 0.75) {
    badge.className = "conf-badge conf-high";
    badge.innerHTML = `<i class="bi bi-check-circle me-1"></i>Alta confianza (${pct}%)`;
    msg.textContent = "Detectamos casi todo. Revisa y ajusta si quieres.";
  } else if (conf >= 0.25) {
    badge.className = "conf-badge conf-med";
    badge.innerHTML = `<i class="bi bi-info-circle me-1"></i>Confianza media (${pct}%)`;
    msg.textContent = "Completamos el resto con valores por defecto. Ajusta lo que necesites.";
  } else {
    badge.className = "conf-badge conf-low";
    badge.innerHTML = `<i class="bi bi-exclamation-circle me-1"></i>Confianza baja (${pct}%)`;
    msg.textContent = "No pudimos interpretar bien el texto. Selecciona los parámetros manualmente.";
  }
}

// ── Step 2 → Step 1 (back) ─────────────────────────────────────────────────────
document.getElementById("backBtn").addEventListener("click", () => setWizardStep(1));

// ── Submit ─────────────────────────────────────────────────────────────────────
document.getElementById("submitBtn").addEventListener("click", async () => {
  hideAlert("alertBox2");

  const energy     = getPill("energyPills");
  const instrument = getPill("instrumentPills");
  if (!energy || !instrument) {
    showAlert("Selecciona energía e instrumento.", "alertBox2");
    return;
  }

  const btn  = document.getElementById("submitBtn");
  const orig = btn.innerHTML;
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Enviando…';

  const fd = new FormData();
  fd.append("audio",       fileInput.files[0]);
  fd.append("genre",       document.getElementById("genre").value);
  fd.append("mood",        document.getElementById("mood").value);
  fd.append("energy",      energy);
  fd.append("instrument",  instrument);
  fd.append("temperature", tempSlider.value);
  fd.append("top_p",       topPSlider.value);

  try {
    const job = await API.submitProcess(fd);
    setWizardStep(3);
    updateSteps(job.status);
    startPolling(job.id);
  } catch (err) {
    showAlert(err.message, "alertBox2");
    btn.disabled = false;
    btn.innerHTML = orig;
  }
});

// ── Progress tracker ───────────────────────────────────────────────────────────
const STEP_ORDER = ["VALIDATING","TRANSCRIBING","GENERATING","COMPLETED","FAILED"];
const STEP_IDS   = {
  VALIDATING:   "step-validating",
  TRANSCRIBING: "step-transcribing",
  GENERATING:   "step-generating",
  COMPLETED:    "step-completed",
};

function updateSteps(status, progressDetail) {
  const idx = STEP_ORDER.indexOf(status);
  Object.entries(STEP_IDS).forEach(([s, id]) => {
    const el   = document.getElementById(id);
    const sIdx = STEP_ORDER.indexOf(s);
    el.classList.remove("active","done");
    if (sIdx < idx)        el.classList.add("done");
    else if (sIdx === idx) el.classList.add("active");
  });

  const msgEl = document.getElementById("statusMsg");
  if (status === "FAILED") {
    msgEl.textContent = "";
  } else if (status === "COMPLETED") {
    msgEl.textContent = "¡Listo! Descarga tus archivos.";
  } else if (status === "GENERATING" && progressDetail) {
    msgEl.innerHTML = `<span class="spinner-wood me-2"></span>${progressDetail}`;
  } else {
    msgEl.textContent = "Este proceso puede tardar unos minutos…";
  }
}

function startPolling(jobId) {
  const interval = setInterval(async () => {
    try {
      const job = await API.pollJob(jobId);
      updateSteps(job.status, job.progress_detail);
      if (job.status === "COMPLETED") {
        clearInterval(interval);
        showResults(job);
      } else if (job.status === "FAILED") {
        clearInterval(interval);
        document.getElementById("errorPanel").classList.remove("d-none");
        document.getElementById("errorMsg").textContent = job.error_message || "Error desconocido.";
      }
    } catch { /* network hiccup */ }
  }, 4000);
}

async function triggerDownload(url, filename) {
  try {
    const res  = await fetch(url);
    const blob = await res.blob();
    const a    = document.createElement("a");
    a.href     = URL.createObjectURL(blob);
    a.download = filename;
    a.click();
    URL.revokeObjectURL(a.href);
  } catch (e) {
    window.open(url, "_blank");
  }
}

function showResults(job) {
  document.getElementById("resultLinks").classList.remove("d-none");
  const midiLink = document.getElementById("midiLink");
  const xmlLink  = document.getElementById("xmlLink");
  if (job.midi_output_url) {
    midiLink.classList.remove("d-none");
    midiLink.addEventListener("click", e => { e.preventDefault(); triggerDownload(job.midi_output_url, "acompanamiento.mid"); });
  }
  if (job.xml_output_url) {
    xmlLink.classList.remove("d-none");
    xmlLink.addEventListener("click", e => { e.preventDefault(); triggerDownload(job.xml_output_url, "partitura.xml"); });
  }
}
