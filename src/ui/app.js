// ===== PARTICLES =====
(function createParticles() {
  const container = document.getElementById("particles");
  for (let i = 0; i < 40; i++) {
    const p = document.createElement("div");
    p.style.cssText = `
      position: absolute;
      width: ${Math.random() * 3 + 1}px;
      height: ${Math.random() * 3 + 1}px;
      background: rgba(99,102,241,${Math.random() * 0.4 + 0.1});
      border-radius: 50%;
      left: ${Math.random() * 100}%;
      top: ${Math.random() * 100}%;
      animation: particleFloat ${Math.random() * 15 + 10}s linear infinite;
      animation-delay: -${Math.random() * 15}s;
    `;
    container.appendChild(p);
  }

  const style = document.createElement("style");
  style.textContent = `
    @keyframes particleFloat {
      0% { transform: translateY(0) translateX(0); opacity: 0; }
      10% { opacity: 1; }
      90% { opacity: 1; }
      100% { transform: translateY(-100vh) translateX(${Math.random() * 100 - 50}px); opacity: 0; }
    }
  `;
  document.head.appendChild(style);
})();

// ===== STATE =====
let currentTab = "upload";
let uploadedFile = null;
let recordedBlob = null;
let mediaRecorder = null;
let audioChunks = [];
let recordingInterval = null;
let recordingSeconds = 0;
let audioContext = null;
let analyser = null;
let animationId = null;

// ===== TABS =====
function switchTab(tab) {
  currentTab = tab;

  document.getElementById("tabUpload").classList.toggle("active", tab === "upload");
  document.getElementById("tabRecord").classList.toggle("active", tab === "record");
  document.getElementById("panelUpload").classList.toggle("hidden", tab !== "upload");
  document.getElementById("panelRecord").classList.toggle("hidden", tab !== "record");

  hideError();
}

// ===== DROP ZONE =====
const dropZone = document.getElementById("dropZone");
const audioFileInput = document.getElementById("audioFile");

dropZone.addEventListener("click", () => audioFileInput.click());

dropZone.addEventListener("dragover", (e) => {
  e.preventDefault();
  dropZone.classList.add("drag-over");
});

dropZone.addEventListener("dragleave", () => dropZone.classList.remove("drag-over"));

dropZone.addEventListener("drop", (e) => {
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

  const url = URL.createObjectURL(file);
  document.getElementById("audioPlayer").src = url;

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

// ===== RECORDER =====
async function toggleRecord() {
  if (mediaRecorder && mediaRecorder.state === "recording") {
    pauseRecord();
  } else {
    await startRecord();
  }
}

async function startRecord() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

    audioContext = new (window.AudioContext || window.webkitAudioContext)();
    analyser = audioContext.createAnalyser();
    analyser.fftSize = 256;
    const source = audioContext.createMediaStreamSource(stream);
    source.connect(analyser);

    mediaRecorder = new MediaRecorder(stream);
    audioChunks = [];

    mediaRecorder.ondataavailable = (e) => {
      if (e.data.size > 0) audioChunks.push(e.data);
    };

    mediaRecorder.onstop = () => {
      recordedBlob = new Blob(audioChunks, { type: "audio/wav" });
      const url = URL.createObjectURL(recordedBlob);
      document.getElementById("recordedAudio").src = url;
      document.getElementById("recordingPreview").classList.remove("hidden");
      stopVisualizer();
    };

    mediaRecorder.start();

    document.getElementById("vizOverlay").classList.add("hidden");
    document.getElementById("btnRecord").classList.add("recording");
    document.getElementById("recordLabel").textContent = "Recording...";
    document.getElementById("btnStop").classList.remove("hidden");

    startTimer();
    drawVisualizer();

  } catch (err) {
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

// ===== TIMER =====
function startTimer() {
  clearInterval(recordingInterval);
  recordingInterval = setInterval(() => {
    recordingSeconds++;
    const m = String(Math.floor(recordingSeconds / 60)).padStart(2, "0");
    const s = String(recordingSeconds % 60).padStart(2, "0");
    document.getElementById("recordTimer").textContent = `${m}:${s}`;
  }, 1000);
}

// ===== VISUALIZER =====
function drawVisualizer() {
  const canvas = document.getElementById("visualizer");
  const ctx = canvas.getContext("2d");
  const bufferLength = analyser.frequencyBinCount;
  const dataArray = new Uint8Array(bufferLength);

  function draw() {
    animationId = requestAnimationFrame(draw);
    analyser.getByteFrequencyData(dataArray);

    ctx.clearRect(0, 0, canvas.width, canvas.height);

    const barWidth = (canvas.width / bufferLength) * 2.5;
    let x = 0;

    for (let i = 0; i < bufferLength; i++) {
      const barHeight = (dataArray[i] / 255) * canvas.height;

      const gradient = ctx.createLinearGradient(0, canvas.height, 0, canvas.height - barHeight);
      gradient.addColorStop(0, "#6366f1");
      gradient.addColorStop(1, "#06b6d4");

      ctx.fillStyle = gradient;
      ctx.beginPath();
      ctx.roundRect(x, canvas.height - barHeight, barWidth - 2, barHeight, 3);
      ctx.fill();

      x += barWidth;
    }
  }

  draw();
}

function stopVisualizer() {
  if (animationId) {
    cancelAnimationFrame(animationId);
    animationId = null;
  }
  const canvas = document.getElementById("visualizer");
  const ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0, canvas.width, canvas.height);
}

// ===== TRANSCRIBE =====
async function transcribe() {
  hideError();

  let fileToSend = null;
  let filename = "";

  if (currentTab === "upload") {
    if (!uploadedFile) {
      showError("Please select an audio file first.");
      return;
    }
    fileToSend = uploadedFile;
    filename = uploadedFile.name;
  } else {
    if (!recordedBlob) {
      showError("Please record audio first.");
      return;
    }
    fileToSend = recordedBlob;
    filename = `recording_${Date.now()}.wav`;
  }

  const btn = document.getElementById("btnTranscribe");
  btn.disabled = true;

  showProgress();
  setStep(1);
  setProgressBar(15);
  setProgressLabel("Uploading audio file...");

  const formData = new FormData();
  formData.append("file", fileToSend, filename);

  try {
    await delay(600);
    setStep(2);
    setProgressBar(50);
    setProgressLabel("AI is processing your audio...");

    const response = await fetch("http://127.0.0.1:8000/api/transcribe", {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      const err = await response.json();
      throw new Error(err.detail || "Transcription failed.");
    }

    const data = await response.json();

    setStep(3);
    setProgressBar(100);
    setProgressLabel("Transcription complete!");

    await delay(800);

    hideProgress();
    showResult(data);

  } catch (err) {
    hideProgress();
    showError(err.message);
  } finally {
    btn.disabled = false;
  }
}

// ===== PROGRESS HELPERS =====
function showProgress() {
  document.getElementById("progressSection").classList.remove("hidden");
}

function hideProgress() {
  document.getElementById("progressSection").classList.add("hidden");
}

function setProgressBar(pct) {
  document.getElementById("progressBar").style.width = pct + "%";
}

function setProgressLabel(text) {
  document.getElementById("progressLabel").textContent = text;
}

function setStep(n) {
  for (let i = 1; i <= 3; i++) {
    const el = document.getElementById(`step${i}`);
    el.classList.remove("active", "done");
    if (i < n) el.classList.add("done");
    else if (i === n) el.classList.add("active");
  }
}

// ===== RESULT =====
function showResult(data) {
  document.getElementById("langResult").textContent = data.language || "Unknown";
  document.getElementById("fileResult").textContent = data.filename || "";
  document.getElementById("transcriptionText").value = data.transcription || "";
  document.getElementById("resultSection").classList.remove("hidden");
  document.getElementById("resultSection").scrollIntoView({ behavior: "smooth" });
}

function copyText() {
  const text = document.getElementById("transcriptionText").value;
  navigator.clipboard.writeText(text).then(() => {
    showToast("Copied to clipboard!");
  });
}

function downloadTxt() {
  const text = document.getElementById("transcriptionText").value;
  const blob = new Blob([text], { type: "text/plain" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "transcription.txt";
  a.click();
  URL.revokeObjectURL(url);
}

function resetAll() {
  clearFile();
  clearRecording();
  document.getElementById("resultSection").classList.add("hidden");
  document.getElementById("transcriptionText").value = "";
  hideError();
  window.scrollTo({ top: 0, behavior: "smooth" });
}

// ===== ERROR =====
function showError(msg) {
  const box = document.getElementById("errorBox");
  document.getElementById("errorMsg").textContent = msg;
  box.classList.remove("hidden");
}

function hideError() {
  document.getElementById("errorBox").classList.add("hidden");
}

// ===== TOAST =====
function showToast(msg) {
  const toast = document.createElement("div");
  toast.textContent = msg;
  toast.style.cssText = `
    position: fixed;
    bottom: 30px;
    right: 30px;
    background: linear-gradient(135deg, #6366f1, #8b5cf6);
    color: white;
    padding: 12px 24px;
    border-radius: 10px;
    font-size: 14px;
    font-weight: 600;
    z-index: 9999;
    animation: fadeUp 0.3s ease;
    box-shadow: 0 8px 25px rgba(99,102,241,0.5);
  `;
  document.body.appendChild(toast);
  setTimeout(() => toast.remove(), 2500);
}

// ===== UTILS =====
function formatBytes(bytes) {
  if (bytes < 1024) return bytes + " B";
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
  return (bytes / (1024 * 1024)).toFixed(1) + " MB";
}

function delay(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}
