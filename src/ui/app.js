/* ============================================================
   TranscriptoSense — app.js  v2.1
   Upgrades:
     • translateText() + loadLanguages() implemented
     • Backend connectivity banner
     • speakers_count displayed in stat card
     • model_used badge showing actual model
     • History card expand/collapse for full transcript
     • Toast notification improvements
     • Waveform icon fix
   ============================================================ */

const API_BASE = "http://127.0.0.1:8000/api";

// ── Global state ──────────────────────────────────────────────
let currentPage  = "transcribe";
let currentTab   = "upload";
let selectedLang = "";           // "" = auto-detect | "fr" | "ar"
let uploadedFile  = null;
let recordedBlob  = null;
let mediaRecorder = null;
let audioChunks   = [];
let recordingInterval = null;
let recordingSeconds  = 0;
let audioContext  = null;
let analyser      = null;
let animationId   = null;
let currentResult = null;        // Last transcription API response
let searchDebounce = null;
let backendOnline = null;        // null = unknown, true/false = checked

// ── Particles ─────────────────────────────────────────────────
(function createParticles() {
  const container = document.getElementById("particles");
  if (!container) return;
  for (let i = 0; i < 40; i++) {
    const p = document.createElement("div");
    p.style.cssText = `
      position:absolute;
      width:${Math.random() * 3 + 1}px;
      height:${Math.random() * 3 + 1}px;
      background:rgba(99,102,241,${Math.random() * 0.4 + 0.1});
      border-radius:50%;
      left:${Math.random() * 100}%;
      top:${Math.random() * 100}%;
      animation:particleFloat ${Math.random() * 15 + 10}s linear infinite;
      animation-delay:-${Math.random() * 15}s;
    `;
    container.appendChild(p);
  }
  const style = document.createElement("style");
  style.textContent = `
    @keyframes particleFloat {
      0%   { transform:translateY(0) translateX(0); opacity:0; }
      10%  { opacity:1; }
      90%  { opacity:1; }
      100% { transform:translateY(-100vh) translateX(${Math.random() * 100 - 50}px); opacity:0; }
    }
  `;
  document.head.appendChild(style);
})();

// ── Backend connectivity check ────────────────────────────────
async function checkBackend() {
  try {
    const res = await fetch(`${API_BASE.replace("/api", "")}/health`, { signal: AbortSignal.timeout(3000) });
    if (res.ok) {
      backendOnline = true;
      hideBanner();
      // Load languages for translation dropdown
      loadLanguages();
      loadStatsBadge();
    } else {
      throw new Error("Non-ok response");
    }
  } catch {
    backendOnline = false;
    showBanner();
  }
}

function showBanner() {
  let banner = document.getElementById("offlineBanner");
  if (!banner) {
    banner = document.createElement("div");
    banner.id = "offlineBanner";
    banner.className = "offline-banner";
    banner.innerHTML = `
      <i class="fas fa-exclamation-triangle"></i>
      <span>Backend server is not running. Start it with:
        <code>uvicorn src.api.main:app --reload</code>
        from the project root.
      </span>
      <button class="banner-retry" onclick="retryConnection()" title="Retry">
        <i class="fas fa-sync-alt"></i> Retry
      </button>
      <button class="banner-dismiss" onclick="hideBanner()" aria-label="Dismiss">&times;</button>
    `;
    document.querySelector(".app").prepend(banner);
  }
  banner.classList.remove("hidden");
}

function hideBanner() {
  const b = document.getElementById("offlineBanner");
  if (b) b.classList.add("hidden");
}

async function retryConnection() {
  const btn = document.querySelector(".banner-retry");
  if (btn) { btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Checking…'; btn.disabled = true; }
  await checkBackend();
  if (btn) { btn.innerHTML = '<i class="fas fa-sync-alt"></i> Retry'; btn.disabled = false; }
}

// ── Language dropdown for translation ────────────────────────
async function loadLanguages() {
  const sel = document.getElementById("targetLang");
  if (!sel) return;
  try {
    const res  = await fetch(`${API_BASE}/languages`);
    const data = await res.json();
    const langs = data.languages || [];
    sel.innerHTML = `<option value="">Select language…</option>` +
      langs.map(l => `<option value="${esc(l.code)}">${esc(l.name)}</option>`).join("");
  } catch {
    // Backend might be offline; keep placeholder option
  }
}

// ── Page switching ─────────────────────────────────────────────
function switchPage(page) {
  currentPage = page;
  document.getElementById("pageTrans").classList.toggle("hidden", page !== "transcribe");
  document.getElementById("pageHistory").classList.toggle("hidden", page !== "history");
  document.getElementById("navTranscribe").classList.toggle("active", page === "transcribe");
  document.getElementById("navHistory").classList.toggle("active", page === "history");
  document.getElementById("navTranscribe").setAttribute("aria-current", page === "transcribe" ? "page" : "false");
  document.getElementById("navHistory").setAttribute("aria-current", page === "history" ? "page" : "false");

  if (page === "history") {
    loadHistory();
  } else {
    loadStatsBadge();
  }
}

// ── Inner tab switching ────────────────────────────────────────
function switchTab(tab) {
  currentTab = tab;
  document.getElementById("tabUpload").classList.toggle("active", tab === "upload");
  document.getElementById("tabRecord").classList.toggle("active", tab === "record");
  document.getElementById("panelUpload").classList.toggle("hidden", tab !== "upload");
  document.getElementById("panelRecord").classList.toggle("hidden", tab !== "record");
  document.getElementById("tabUpload").setAttribute("aria-selected", tab === "upload");
  document.getElementById("tabRecord").setAttribute("aria-selected", tab === "record");
  hideError();
}

// ── Language selector ─────────────────────────────────────────
function selectLang(btn) {
  document.querySelectorAll(".lang-btn").forEach(b => b.classList.remove("active"));
  btn.classList.add("active");
  selectedLang = btn.dataset.lang || "";
}

// ── Drop zone ─────────────────────────────────────────────────
const dropZone      = document.getElementById("dropZone");
const audioFileInput = document.getElementById("audioFile");

dropZone.addEventListener("click", () => audioFileInput.click());

dropZone.addEventListener("dragover", e => {
  e.preventDefault();
  dropZone.classList.add("drag-over");
});

dropZone.addEventListener("dragleave", () => dropZone.classList.remove("drag-over"));

dropZone.addEventListener("drop", e => {
  e.preventDefault();
  dropZone.classList.remove("drag-over");
  const file = e.dataTransfer.files[0];
  if (file) handleFileSelect(file);
});

audioFileInput.addEventListener("change", () => {
  if (audioFileInput.files[0]) handleFileSelect(audioFileInput.files[0]);
});

function handleFileSelect(file) {
  const allowed = [".wav", ".mp3", ".m4a", ".flac", ".ogg"];
  const ext = "." + file.name.split(".").pop().toLowerCase();
  if (!allowed.includes(ext)) {
    showError(`Unsupported format: ${ext}. Please use WAV, MP3, M4A, FLAC or OGG.`);
    return;
  }
  uploadedFile = file;
  document.getElementById("fileName").textContent = file.name;
  document.getElementById("fileSize").textContent = formatBytes(file.size);
  document.getElementById("audioPlayer").src = URL.createObjectURL(file);
  document.getElementById("dropZone").classList.add("hidden");
  document.getElementById("filePreview").classList.remove("hidden");
  hideError();
}

function clearFile() {
  uploadedFile = null;
  audioFileInput.value = "";
  document.getElementById("audioPlayer").src = "";
  document.getElementById("dropZone").classList.remove("hidden");
  document.getElementById("filePreview").classList.add("hidden");
}

// ── Recorder ──────────────────────────────────────────────────
async function toggleRecord() {
  if (mediaRecorder && mediaRecorder.state === "recording") pauseRecord();
  else await startRecord();
}

async function startRecord() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    audioContext = new (window.AudioContext || window.webkitAudioContext)();
    analyser = audioContext.createAnalyser();
    analyser.fftSize = 256;
    audioContext.createMediaStreamSource(stream).connect(analyser);

    mediaRecorder = new MediaRecorder(stream);
    audioChunks = [];

    mediaRecorder.ondataavailable = e => { if (e.data.size > 0) audioChunks.push(e.data); };

    mediaRecorder.onstop = () => {
      recordedBlob = new Blob(audioChunks, { type: "audio/wav" });
      document.getElementById("recordedAudio").src = URL.createObjectURL(recordedBlob);
      document.getElementById("recordingPreview").classList.remove("hidden");
      stopVisualizer();
    };

    mediaRecorder.start();
    document.getElementById("vizOverlay").classList.add("hidden");
    document.getElementById("btnRecord").classList.add("recording");
    document.getElementById("recordLabel").textContent = "Recording…";
    document.getElementById("btnStop").classList.remove("hidden");
    startTimer();
    drawVisualizer();
  } catch {
    showError("Microphone access denied. Please allow microphone access in your browser.");
  }
}

function pauseRecord() {
  if (mediaRecorder && mediaRecorder.state === "recording") {
    mediaRecorder.pause();
    document.getElementById("recordLabel").textContent = "Paused";
    document.getElementById("btnRecord").classList.remove("recording");
    clearInterval(recordingInterval);
  }
}

function stopRecord() {
  if (mediaRecorder) {
    mediaRecorder.stop();
    mediaRecorder.stream.getTracks().forEach(t => t.stop());
  }
  clearInterval(recordingInterval);
  document.getElementById("btnRecord").classList.remove("recording");
  document.getElementById("recordLabel").textContent = "Record";
  document.getElementById("btnStop").classList.add("hidden");
  document.getElementById("vizOverlay").classList.remove("hidden");
}

function clearRecording() {
  recordedBlob = null;
  recordingSeconds = 0;
  document.getElementById("recordTimer").textContent = "00:00";
  document.getElementById("recordedAudio").src = "";
  document.getElementById("recordingPreview").classList.add("hidden");
}

// ── Timer ─────────────────────────────────────────────────────
function startTimer() {
  clearInterval(recordingInterval);
  recordingInterval = setInterval(() => {
    recordingSeconds++;
    const m = String(Math.floor(recordingSeconds / 60)).padStart(2, "0");
    const s = String(recordingSeconds % 60).padStart(2, "0");
    document.getElementById("recordTimer").textContent = `${m}:${s}`;
  }, 1000);
}

// ── Visualizer ────────────────────────────────────────────────
function drawVisualizer() {
  const canvas = document.getElementById("visualizer");
  const ctx    = canvas.getContext("2d");
  const buf    = new Uint8Array(analyser.frequencyBinCount);

  function draw() {
    animationId = requestAnimationFrame(draw);
    analyser.getByteFrequencyData(buf);
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    const bw = (canvas.width / buf.length) * 2.5;
    let x = 0;
    buf.forEach(v => {
      const h = (v / 255) * canvas.height;
      const g = ctx.createLinearGradient(0, canvas.height, 0, canvas.height - h);
      g.addColorStop(0, "#6366f1");
      g.addColorStop(1, "#06b6d4");
      ctx.fillStyle = g;
      ctx.beginPath();
      ctx.roundRect(x, canvas.height - h, bw - 2, h, 3);
      ctx.fill();
      x += bw;
    });
  }
  draw();
}

function stopVisualizer() {
  if (animationId) { cancelAnimationFrame(animationId); animationId = null; }
  const canvas = document.getElementById("visualizer");
  canvas.getContext("2d").clearRect(0, 0, canvas.width, canvas.height);
}

// ── Transcribe ────────────────────────────────────────────────
async function transcribe() {
  hideError();

  let fileToSend = null;
  let filename   = "";

  if (currentTab === "upload") {
    if (!uploadedFile) { showError("Please select an audio file first."); return; }
    fileToSend = uploadedFile;
    filename   = uploadedFile.name;
  } else {
    if (!recordedBlob) { showError("Please record audio first."); return; }
    fileToSend = recordedBlob;
    filename   = `recording_${Date.now()}.wav`;
  }

  const btn = document.getElementById("btnTranscribe");
  btn.disabled = true;

  showProgress();
  setStep(1); setProgressBar(15); setProgressLabel("Uploading audio file…");

  const fd = new FormData();
  fd.append("file", fileToSend, filename);
  if (selectedLang) fd.append("language", selectedLang);

  try {
    await delay(500);
    setStep(2); setProgressBar(45); setProgressLabel("AI is transcribing your audio…");

    const res = await fetch(`${API_BASE}/transcribe`, { method: "POST", body: fd });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Transcription failed.");
    }

    const data = await res.json();
    currentResult = data;

    setStep(3); setProgressBar(100); setProgressLabel("Transcription complete!");
    await delay(700);

    hideProgress();
    showResult(data);
    loadStatsBadge();
    backendOnline = true;
    hideBanner();

  } catch (err) {
    hideProgress();
    if (err.message.includes("Failed to fetch") || err.message.includes("NetworkError")) {
      showError("Cannot reach backend. Make sure the server is running on port 8000.");
      showBanner();
    } else {
      showError(err.message);
    }
  } finally {
    btn.disabled = false;
  }
}

// ── Progress helpers ──────────────────────────────────────────
function showProgress() { document.getElementById("progressSection").classList.remove("hidden"); }
function hideProgress() { document.getElementById("progressSection").classList.add("hidden"); }
function setProgressBar(pct) { document.getElementById("progressBar").style.width = pct + "%"; }
function setProgressLabel(t) { document.getElementById("progressLabel").textContent = t; }

function setStep(n) {
  for (let i = 1; i <= 3; i++) {
    const el = document.getElementById(`step${i}`);
    el.classList.remove("active", "done");
    if (i < n) el.classList.add("done");
    else if (i === n) el.classList.add("active");
  }
}

// ── Result display ────────────────────────────────────────────
function showResult(data) {
  const text = data.transcription || "";
  const isArabic = detectRTL(text);

  // Stats cards
  document.getElementById("scLang").textContent     = data.language || "Unknown";
  document.getElementById("scWords").textContent    = countWords(text).toLocaleString();
  document.getElementById("scChars").textContent    = text.length.toLocaleString();
  document.getElementById("scDur").textContent      = formatDuration(data.duration_sec || 0);
  document.getElementById("scSize").textContent     = data.file_size  || "—";
  const speakersEl = document.getElementById("scSpeakers");
  if (speakersEl) {
    speakersEl.textContent = data.has_diarization
      ? (data.speakers_count > 0 ? data.speakers_count : "—")
      : "—";
  }

  // File badge
  document.getElementById("fileResult").textContent = data.filename || "";

  // Model badge — show actual model used
  const modelEl = document.getElementById("modelResult");
  if (modelEl) {
    modelEl.textContent = data.model_used || "whisper-small";
    const modelBadge = document.getElementById("badgeModel");
    if (modelBadge) {
      const isDeepgram = (data.model_used || "").includes("deepgram");
      modelBadge.className = `meta-badge ${isDeepgram ? "meta-badge-deepgram" : "meta-badge-model"}`;
    }
  }

  // Transcription textarea
  const area = document.getElementById("transcriptionText");
  area.value = text;
  area.classList.toggle("rtl", isArabic);

  // Show/hide translation panel based on whether text exists
  const transPanel = document.getElementById("translationPanel");
  if (transPanel) {
    transPanel.classList.toggle("hidden", !text.trim());
    // Reset translation result
    const translatedResult = document.getElementById("translatedResult");
    if (translatedResult) translatedResult.classList.add("hidden");
    const translatedText = document.getElementById("translatedText");
    if (translatedText) translatedText.value = "";
  }

  // Show section
  const section = document.getElementById("resultSection");
  section.classList.remove("hidden");
  section.scrollIntoView({ behavior: "smooth", block: "start" });
}

// ── Translation ───────────────────────────────────────────────
async function translateText() {
  const text   = document.getElementById("transcriptionText").value;
  const target = document.getElementById("targetLang").value;

  if (!text.trim()) { showToast("No transcription text to translate.", "error"); return; }
  if (!target)      { showToast("Please select a target language.", "error"); return; }

  const btn   = document.getElementById("btnTranslate");
  const label = document.getElementById("translateLabel");
  btn.disabled = true;
  if (label) label.textContent = "Translating…";

  try {
    const res = await fetch(`${API_BASE}/translate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, target }),
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Translation failed.");
    }

    const data = await res.json();
    const translated = data.translated_text || "";

    document.getElementById("translatedText").value = translated;
    document.getElementById("translatedText").classList.toggle("rtl", detectRTL(translated));

    // Show the translated badge
    const badge = document.getElementById("translatedBadge");
    if (badge) {
      const langName = document.getElementById("targetLang").options[
        document.getElementById("targetLang").selectedIndex
      ].text;
      badge.textContent = `→ ${langName}`;
    }

    document.getElementById("translatedResult").classList.remove("hidden");
    showToast("Translation complete!", "success");

  } catch (err) {
    showToast(`Translation failed: ${err.message}`, "error");
  } finally {
    btn.disabled = false;
    if (label) label.textContent = "Translate";
  }
}

function copyTranslation() {
  const text = document.getElementById("translatedText").value;
  if (!text) return;
  navigator.clipboard.writeText(text).then(() => showToast("Translation copied!", "success"));
}

// ── Copy ─────────────────────────────────────────────────────
function copyText() {
  const text = document.getElementById("transcriptionText").value;
  navigator.clipboard.writeText(text).then(() => showToast("Copied to clipboard!", "success"));
}

// ── Export: TXT ───────────────────────────────────────────────
function exportTXT() {
  if (!currentResult) return;
  const d = currentResult;
  const dur = formatDuration(d.duration_sec || 0);
  const ts  = new Date().toLocaleString();
  const content = [
    "TRANSCRIPTOSENSE — Transcription Report",
    "=".repeat(46),
    `Filename   : ${d.filename}`,
    `Language   : ${d.language}`,
    `Model      : ${d.model_used || "whisper-small"}`,
    `File Size  : ${d.file_size || "—"}`,
    `Duration   : ${dur}`,
    `Words      : ${countWords(d.transcription || "")}`,
    `Generated  : ${ts}`,
    "=".repeat(46),
    "",
    d.transcription || "",
  ].join("\n");

  downloadBlob(new Blob([content], { type: "text/plain;charset=utf-8" }),
    `${baseName(d.filename)}_transcription.txt`);
  showToast("TXT exported!", "success");
}

// ── Export: JSON ──────────────────────────────────────────────
function exportJSON() {
  if (!currentResult) return;
  const payload = {
    id:              currentResult.id,
    filename:        currentResult.filename,
    language:        currentResult.language,
    model_used:      currentResult.model_used || "whisper-small",
    file_size:       currentResult.file_size,
    duration_sec:    currentResult.duration_sec,
    speakers_count:  currentResult.speakers_count,
    has_diarization: currentResult.has_diarization,
    word_count:      countWords(currentResult.transcription || ""),
    char_count:      (currentResult.transcription || "").length,
    generated_at:    new Date().toISOString(),
    transcription:   currentResult.transcription,
  };
  downloadBlob(new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" }),
    `${baseName(currentResult.filename)}_transcription.json`);
  showToast("JSON exported!", "success");
}

// ── Export: PDF ───────────────────────────────────────────────
function exportPDF() {
  if (!currentResult) return;
  if (!window.jspdf) { showToast("jsPDF not loaded. Check your connection.", "error"); return; }

  const { jsPDF } = window.jspdf;
  const doc = new jsPDF({ orientation: "portrait", unit: "mm", format: "a4" });
  const pw  = doc.internal.pageSize.getWidth();
  const ph  = doc.internal.pageSize.getHeight();
  const mg  = 20;
  const cw  = pw - mg * 2;

  // ── Header band ─────────────────────────────────────────────
  doc.setFillColor(99, 102, 241);
  doc.rect(0, 0, pw, 38, "F");

  doc.setTextColor(255, 255, 255);
  doc.setFont("helvetica", "bold");
  doc.setFontSize(20);
  doc.text("TranscriptoSense", mg, 20);

  doc.setFont("helvetica", "normal");
  doc.setFontSize(10);
  doc.text("AI Transcription Report", mg, 30);

  // ── Accent bar ───────────────────────────────────────────────
  doc.setFillColor(6, 182, 212);
  doc.rect(0, 38, pw, 2.5, "F");

  let y = 54;
  doc.setTextColor(30, 30, 40);

  // ── Metadata table ───────────────────────────────────────────
  const meta = [
    ["File",       currentResult.filename],
    ["Language",   currentResult.language],
    ["Model",      currentResult.model_used || "whisper-small"],
    ["File Size",  currentResult.file_size || "—"],
    ["Duration",   formatDuration(currentResult.duration_sec || 0)],
    ["Words",      countWords(currentResult.transcription || "").toLocaleString()],
    ["Generated",  new Date().toLocaleString()],
  ];

  meta.forEach(([key, val], rowIdx) => {
    if (rowIdx % 2 === 0) {
      doc.setFillColor(245, 245, 252);
      doc.rect(mg - 2, y - 5, cw + 4, 9, "F");
    }
    doc.setFont("helvetica", "bold");
    doc.setFontSize(10);
    doc.setTextColor(99, 102, 241);
    doc.text(key + ":", mg, y);
    doc.setFont("helvetica", "normal");
    doc.setTextColor(30, 30, 40);
    doc.text(String(val), mg + 32, y);
    y += 10;
  });

  // ── Divider ──────────────────────────────────────────────────
  y += 4;
  doc.setDrawColor(220, 220, 230);
  doc.setLineWidth(0.5);
  doc.line(mg, y, pw - mg, y);
  y += 8;

  // ── Transcription section header ─────────────────────────────
  doc.setFont("helvetica", "bold");
  doc.setFontSize(12);
  doc.setTextColor(99, 102, 241);
  doc.text("Transcription", mg, y);
  y += 8;

  // ── Transcription body ───────────────────────────────────────
  doc.setFont("helvetica", "normal");
  doc.setFontSize(11);
  doc.setTextColor(40, 40, 55);

  const lines = doc.splitTextToSize(currentResult.transcription || "(empty)", cw);
  lines.forEach(line => {
    if (y > ph - mg - 10) {
      doc.addPage();
      y = mg;
      doc.setFillColor(99, 102, 241);
      doc.rect(0, 0, pw, 12, "F");
      doc.setFont("helvetica", "bold");
      doc.setFontSize(9);
      doc.setTextColor(255, 255, 255);
      doc.text("TranscriptoSense — continued", mg, 8);
      doc.setFont("helvetica", "normal");
      doc.setFontSize(11);
      doc.setTextColor(40, 40, 55);
      y = 22;
    }
    doc.text(line, mg, y);
    y += 7;
  });

  // ── Footer on each page ──────────────────────────────────────
  const totalPages = doc.internal.getNumberOfPages();
  for (let i = 1; i <= totalPages; i++) {
    doc.setPage(i);
    doc.setFillColor(245, 245, 252);
    doc.rect(0, ph - 12, pw, 12, "F");
    doc.setFont("helvetica", "normal");
    doc.setFontSize(8);
    doc.setTextColor(140, 140, 160);
    doc.text(`TranscriptoSense © ${new Date().getFullYear()}`, mg, ph - 4);
    doc.text(`Page ${i} / ${totalPages}`, pw - mg, ph - 4, { align: "right" });
  }

  doc.save(`${baseName(currentResult.filename)}_transcription.pdf`);
  showToast("PDF exported!", "success");
}

// ── Reset ─────────────────────────────────────────────────────
function resetAll() {
  clearFile();
  clearRecording();
  currentResult = null;
  document.getElementById("resultSection").classList.add("hidden");
  document.getElementById("transcriptionText").value = "";
  const translatedResult = document.getElementById("translatedResult");
  if (translatedResult) translatedResult.classList.add("hidden");
  hideError();
  window.scrollTo({ top: 0, behavior: "smooth" });
}

// ── Error ─────────────────────────────────────────────────────
function showError(msg) {
  document.getElementById("errorMsg").textContent = msg;
  document.getElementById("errorBox").classList.remove("hidden");
}

function hideError() {
  document.getElementById("errorBox").classList.add("hidden");
}

// ── Toast ─────────────────────────────────────────────────────
function showToast(msg, type = "default") {
  const t = document.createElement("div");
  t.className = "toast-msg";
  if (type === "success") t.classList.add("success-toast");
  if (type === "error")   t.classList.add("error-toast");
  const icon = type === "success" ? "check-circle" : type === "error" ? "exclamation-circle" : "info-circle";
  t.innerHTML = `<i class="fas fa-${icon}"></i> ${esc(msg)}`;
  document.body.appendChild(t);
  // Animate in
  requestAnimationFrame(() => t.classList.add("toast-visible"));
  setTimeout(() => {
    t.classList.remove("toast-visible");
    t.classList.add("toast-hiding");
    setTimeout(() => t.remove(), 350);
  }, 2800);
}

// ═══════════════════════════════════════════════════════════════
//  HISTORY
// ═══════════════════════════════════════════════════════════════

async function loadHistory() {
  const list = document.getElementById("historyList");
  list.innerHTML = renderSkeletons(3);
  document.getElementById("historyEmpty").classList.add("hidden");

  try {
    const res  = await fetch(`${API_BASE}/history`);
    const data = await res.json();
    renderHistoryCards(data.records || [], data.total);
    updateBadge(data.total);
    document.getElementById("statTotal").textContent = data.total;
  } catch {
    list.innerHTML = "";
    showToast("Could not load history. Is the backend running?", "error");
  }
}

async function loadStatsBadge() {
  try {
    const res  = await fetch(`${API_BASE}/history`);
    const data = await res.json();
    updateBadge(data.total);
    document.getElementById("statTotal").textContent = data.total;
  } catch { /* silent */ }
}

function updateBadge(n) {
  document.getElementById("historyBadge").textContent = n;
}

function renderHistoryCards(records, total) {
  const list  = document.getElementById("historyList");
  const empty = document.getElementById("historyEmpty");
  const label = document.getElementById("historyCountLabel");

  list.innerHTML = "";

  if (!records.length) {
    empty.classList.remove("hidden");
    label.textContent = "";
    return;
  }

  empty.classList.add("hidden");
  label.textContent = `${total} transcription${total !== 1 ? "s" : ""} found`;

  records.forEach((r, i) => {
    const preview  = (r.transcription || "").slice(0, 200) + ((r.transcription || "").length > 200 ? "…" : "");
    const isRTL    = detectRTL(r.transcription || "");
    const dur      = formatDuration(r.duration_sec || 0);
    const dateStr  = formatDate(r.created_at);
    const isDeepgram = (r.model_used || "").includes("deepgram");
    const modelIcon  = isDeepgram ? "fa-bolt" : "fa-robot";
    const modelClass = isDeepgram ? "hbadge-deepgram" : "hbadge-model";

    const card = document.createElement("div");
    card.className = "history-card";
    card.style.animationDelay = `${i * 0.06}s`;
    card.innerHTML = `
      <div class="history-card-top">
        <div class="history-card-title">
          <i class="fas fa-file-audio"></i>
          <span class="history-card-name" title="${esc(r.filename)}">${esc(r.filename)}</span>
        </div>
        <div class="history-card-badges">
          <span class="hbadge hbadge-lang"><i class="fas fa-globe"></i>${esc(r.language || "Unknown")}</span>
          <span class="hbadge ${modelClass}"><i class="fas ${modelIcon}"></i>${esc(r.model_used || "whisper")}</span>
          ${r.has_diarization ? `<span class="hbadge hbadge-diar"><i class="fas fa-users"></i>${r.speakers_count || "?"} speakers</span>` : ""}
        </div>
      </div>
      <div class="history-card-preview${isRTL ? " rtl" : ""}" 
           onclick="toggleExpand(this)" 
           title="Click to expand/collapse"
           style="cursor:pointer">
        <span class="preview-text">${esc(preview) || "<em>No transcription text</em>"}</span>
        ${(r.transcription || "").length > 200 ? `
        <div class="full-text hidden${isRTL ? " rtl" : ""}">
          ${esc(r.transcription || "")}
        </div>
        <span class="expand-hint"><i class="fas fa-chevron-down"></i> Show more</span>` : ""}
      </div>
      <div class="history-card-meta">
        <span><i class="fas fa-calendar-alt"></i>${dateStr}</span>
        ${r.file_size ? `<span><i class="fas fa-weight-hanging"></i>${esc(r.file_size)}</span>` : ""}
        ${r.duration_sec ? `<span><i class="fas fa-clock"></i>${dur}</span>` : ""}
        <span><i class="fas fa-font"></i>${countWords(r.transcription || "").toLocaleString()} words</span>
      </div>
      <div class="history-card-actions">
        <button class="hact-btn" onclick="downloadRecord(${r.id})">
          <i class="fas fa-download"></i> TXT
        </button>
        <button class="hact-btn" onclick="exportHistoryJSON(${r.id})">
          <i class="fas fa-code"></i> JSON
        </button>
        <button class="hact-btn del-btn" onclick="deleteRecord(${r.id}, this)">
          <i class="fas fa-trash"></i> Delete
        </button>
      </div>
    `;
    list.appendChild(card);
  });
}

function toggleExpand(el) {
  const fullText  = el.querySelector(".full-text");
  const hint      = el.querySelector(".expand-hint");
  const previewSpan = el.querySelector(".preview-text");
  if (!fullText) return;

  const isExpanded = !fullText.classList.contains("hidden");
  fullText.classList.toggle("hidden", isExpanded);
  if (previewSpan) previewSpan.classList.toggle("hidden", !isExpanded);
  if (hint) {
    hint.innerHTML = isExpanded
      ? '<i class="fas fa-chevron-down"></i> Show more'
      : '<i class="fas fa-chevron-up"></i> Show less';
  }
}

function renderSkeletons(n) {
  return Array.from({ length: n }, () => `
    <div class="skeleton-card">
      <div class="skel" style="height:16px;width:55%;"></div>
      <div class="skel" style="height:12px;width:85%;"></div>
      <div class="skel" style="height:12px;width:70%;"></div>
      <div class="skel" style="height:10px;width:40%;"></div>
    </div>
  `).join("");
}

// ── Search ────────────────────────────────────────────────────
function onSearchInput(q) {
  clearTimeout(searchDebounce);
  const clearBtn = document.getElementById("btnClearSearch");
  clearBtn.classList.toggle("hidden", !q);

  if (!q || q.length < 2) {
    searchDebounce = setTimeout(loadHistory, 300);
    return;
  }

  searchDebounce = setTimeout(async () => {
    const list = document.getElementById("historyList");
    list.innerHTML = renderSkeletons(2);
    try {
      const res  = await fetch(`${API_BASE}/history/search?q=${encodeURIComponent(q)}`);
      const data = await res.json();
      renderHistoryCards(data.records || [], data.total);
    } catch {
      list.innerHTML = "";
      showToast("Search failed.", "error");
    }
  }, 350);
}

function clearSearch() {
  document.getElementById("historySearch").value = "";
  document.getElementById("btnClearSearch").classList.add("hidden");
  loadHistory();
}

// ── Delete one ────────────────────────────────────────────────
async function deleteRecord(id, btn) {
  if (!confirm("Delete this transcription? This cannot be undone.")) return;
  try {
    const res = await fetch(`${API_BASE}/history/${id}`, { method: "DELETE" });
    if (!res.ok) throw new Error();
    const card = btn.closest(".history-card");
    card.style.transition = "opacity 0.3s, transform 0.3s";
    card.style.opacity    = "0";
    card.style.transform  = "translateX(30px)";
    setTimeout(() => { card.remove(); loadStatsBadge(); }, 320);
    showToast("Transcription deleted.", "success");
  } catch {
    showToast("Delete failed.", "error");
  }
}

// ── Clear all ─────────────────────────────────────────────────
async function clearAllHistory() {
  const countEl = document.getElementById("historyCountLabel");
  const countText = countEl.textContent || "";
  if (!confirm(`Clear ALL transcriptions? ${countText}. This cannot be undone.`)) return;
  try {
    const res = await fetch(`${API_BASE}/history`, { method: "DELETE" });
    if (!res.ok) throw new Error();
    loadHistory();
    loadStatsBadge();
    showToast("All transcriptions cleared.", "success");
  } catch {
    showToast("Clear failed.", "error");
  }
}

// ── Download TXT (from history) ───────────────────────────────
function downloadRecord(id) {
  window.open(`${API_BASE}/history/${id}/download`, "_blank");
}

// ── Export history record as JSON ─────────────────────────────
async function exportHistoryJSON(id) {
  try {
    const res  = await fetch(`${API_BASE}/history/${id}`);
    const data = await res.json();
    const payload = {
      ...data,
      word_count: countWords(data.transcription || ""),
      char_count: (data.transcription || "").length,
      exported_at: new Date().toISOString(),
    };
    downloadBlob(new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" }),
      `transcription_${id}.json`);
    showToast("JSON exported!", "success");
  } catch {
    showToast("Export failed.", "error");
  }
}

// ═══════════════════════════════════════════════════════════════
//  UTILITIES
// ═══════════════════════════════════════════════════════════════

function formatBytes(bytes) {
  if (bytes < 1024)            return bytes + " B";
  if (bytes < 1024 * 1024)    return (bytes / 1024).toFixed(1) + " KB";
  return (bytes / (1024 * 1024)).toFixed(1) + " MB";
}

function formatDuration(sec) {
  if (!sec || sec <= 0) return "—";
  const m = Math.floor(sec / 60);
  const s = Math.round(sec % 60);
  return m ? `${m}m ${String(s).padStart(2, "0")}s` : `${s}s`;
}

function formatDate(str) {
  if (!str) return "—";
  try {
    return new Date(str).toLocaleString(undefined, {
      year: "numeric", month: "short", day: "numeric",
      hour: "2-digit", minute: "2-digit"
    });
  } catch { return str; }
}

function countWords(text) {
  return text.trim() ? text.trim().split(/\s+/).length : 0;
}

function detectRTL(text) {
  const rtlRe = /[\u0600-\u06FF\u0750-\u077F\u0590-\u05FF]/;
  const rtlChars = (text.match(new RegExp(rtlRe.source, "g")) || []).length;
  return rtlChars / (text.length || 1) > 0.3;
}

function baseName(filename) {
  return (filename || "transcription").replace(/\.[^.]+$/, "").replace(/\s+/g, "_");
}

function esc(str) {
  return String(str)
    .replace(/&/g,"&amp;")
    .replace(/</g,"&lt;")
    .replace(/>/g,"&gt;")
    .replace(/"/g,"&quot;");
}

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a   = document.createElement("a");
  a.href    = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

function delay(ms) { return new Promise(r => setTimeout(r, ms)); }

// ── Init ──────────────────────────────────────────────────────
checkBackend();
