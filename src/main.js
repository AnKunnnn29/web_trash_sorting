import { trashItems } from './mockData.js';
import { sound } from './sound.js';
import { captureWebcamFrame, getCroppedCanvas } from './cameraFrame.js';
import { setupHardwareConnection } from './hardwareConnection.js';
import { setupSimulationPanel } from './simulationPanel.js';
import { setupWorldEffects } from './worldEffects.js';
import {
  callGeminiVision,
  findTrashItemByLabel,
  getTopScores,
  loadConfiguredAIEngine
} from './aiEngines.js';

// Application State
let appState = 'welcome'; // welcome, idle, instructing, correct, incorrect
let currentItem = null;
let scoreCorrect = 0;
let scoreTotal = 0;
let model = null;
let isCustomModel = false;
let isModelLoading = true;
let isScanningActive = false;
let currentWebcamStream = null;

// AI Smoothing & Threshold parameters
let aiThreshold = 0.35;
let lastPredictedItem = null; // Vật thể đang nhìn thấy hiện tại

// Gemini API status
let isGeminiActive = false;

// ── Auto-scan state machine ──────────────────────────────────────────────────
// Cơ chế: AI phải nhìn thấy cùng 1 vật thể ổn định trong AUTO_CONFIRM_MS ms
// trước khi tự động kích hoạt scan → tránh nhận diện nhầm khi bé đưa tay qua
const AUTO_CONFIRM_MS   = 700;   // Thời gian giữ ổn định để xác nhận
const AUTO_COOLDOWN_MS  = 1500;  // Thời gian chờ sau mỗi lần scan thành công (1.5s)
const AUTO_PREVIEW_MS   = 180;   // Tần suất chạy vòng lặp preview
const API_PREVIEW_MS    = 450;   // Giảm tải cho Python API khi preview webcam
const PREDICTION_WINDOW = 5;     // Số frame dùng để lọc nhiễu
const MIN_STABLE_VOTES  = 3;     // Cần ít nhất 3/5 frame cùng nhãn
const MIN_CONF_MARGIN   = 0.08;  // Top-1 phải cách top-2 tối thiểu 8%

let autoScanCandidateId  = null;  // ID của vật thể đang được "chờ xác nhận"
let autoScanCandidateSince = 0;   // Timestamp bắt đầu nhìn thấy vật thể đó
let autoScanCooldownUntil  = 0;   // Timestamp kết thúc cooldown
let isAutoScanEnabled      = true; // Luôn bật tự động (không có toggle nữa)
let predictionHistory      = [];

// Confetti Particle System
class Confetti {
  constructor(canvas) {
    this.canvas = canvas;
    this.ctx = canvas.getContext('2d');
    this.particles = [];
    this.animationId = null;
    this.colors = ['#FFC107', '#4CAF50', '#00BCD4', '#E91E63', '#9C27B0', '#FF5722'];
  }
  
  resize() {
    const rect = this.canvas.parentElement.getBoundingClientRect();
    this.canvas.width = rect.width;
    this.canvas.height = rect.height;
  }
  
  start() {
    this.resize();
    this.particles = [];
    for (let i = 0; i < 80; i++) {
      this.particles.push({
        x: Math.random() * this.canvas.width,
        y: Math.random() * -50 - 10,
        size: Math.random() * 8 + 6,
        color: this.colors[Math.floor(Math.random() * this.colors.length)],
        speedX: Math.random() * 4 - 2,
        speedY: Math.random() * 3 + 3,
        rotation: Math.random() * 360,
        rotationSpeed: Math.random() * 10 - 5
      });
    }
    
    if (this.animationId) cancelAnimationFrame(this.animationId);
    this.animate();
  }
  
  stop() {
    if (this.animationId) {
      cancelAnimationFrame(this.animationId);
      this.animationId = null;
    }
    this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
  }
  
  animate() {
    this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
    let active = false;
    
    this.particles.forEach(p => {
      p.x += p.speedX;
      p.y += p.speedY;
      p.rotation += p.rotationSpeed;
      
      this.ctx.save();
      this.ctx.translate(p.x, p.y);
      this.ctx.rotate((p.rotation * Math.PI) / 180);
      this.ctx.fillStyle = p.color;
      this.ctx.fillRect(-p.size / 2, -p.size / 2, p.size, p.size);
      this.ctx.restore();
      
      if (p.y < this.canvas.height) {
        active = true;
      }
    });
    
    if (active) {
      this.animationId = requestAnimationFrame(() => this.animate());
    } else {
      this.stop();
    }
  }
}

let confettiEffect = null;

// Initialize app when DOM loaded
document.addEventListener('DOMContentLoaded', () => {
  setupUI();
  setupWorldEffects();
  setupCamera();
  loadAIModel();
  setupWebSocket();
  setupSimulationPanel({
    onScanItem: triggerTrashScan,
    onSelectCategory: handleSelectedCategory,
    onResetScore: resetScore,
    onResetGame: resetGame
  });
});

// Setup DOM UI Elements and events
function setupUI() {
  const canvas = document.getElementById('confetti-canvas');
  if (canvas) {
    confettiEffect = new Confetti(canvas);
    window.addEventListener('resize', () => {
      if (appState === 'correct') confettiEffect.resize();
    });
  }

  // Bind settings popover events
  const btnSaveSettings = document.getElementById('btn-save-settings');
  const espIpInput = document.getElementById('esp-ip');
  const aiModelUrlInput = document.getElementById('ai-model-url');
  const pythonApiUrlInput = document.getElementById('python-api-url');
  const geminiApiKeyInput = document.getElementById('gemini-api-key');
  const aiThresholdInput = document.getElementById('ai-threshold');
  const thresholdValLabel = document.getElementById('threshold-val');
  
  // Load saved configurations
  const savedIp = localStorage.getItem('esp32_ip') || '';
  if (espIpInput) espIpInput.value = savedIp;

  const savedModelUrl = localStorage.getItem('ai_model_url') || '';
  if (aiModelUrlInput) aiModelUrlInput.value = savedModelUrl;

  const savedPythonApiUrl = localStorage.getItem('python_api_url') || 'http://localhost:5000';
  if (pythonApiUrlInput) pythonApiUrlInput.value = savedPythonApiUrl;

  const savedGeminiKey = localStorage.getItem('gemini_api_key') || '';
  if (geminiApiKeyInput) geminiApiKeyInput.value = savedGeminiKey;

  const defaultVal = savedGeminiKey ? '75' : (savedModelUrl ? '75' : '35'); 
  const savedThreshold = localStorage.getItem('ai_threshold') || defaultVal;
  aiThreshold = parseFloat(savedThreshold) / 100;
  if (aiThresholdInput) aiThresholdInput.value = savedThreshold;
  if (thresholdValLabel) thresholdValLabel.innerText = `${savedThreshold}%`;

  // Dynamically update threshold text as slider moves
  if (aiThresholdInput && thresholdValLabel) {
    aiThresholdInput.addEventListener('input', (e) => {
      thresholdValLabel.innerText = `${e.target.value}%`;
    });
  }

  if (btnSaveSettings) {
    btnSaveSettings.addEventListener('click', () => {
      const ip = espIpInput.value.trim();
      const modelUrl = aiModelUrlInput.value.trim();
      const pythonApiUrl = pythonApiUrlInput ? pythonApiUrlInput.value.trim() : 'http://localhost:5000';
      const geminiKey = geminiApiKeyInput ? geminiApiKeyInput.value.trim() : '';
      const thresholdVal = aiThresholdInput.value;
      
      localStorage.setItem('esp32_ip', ip);
      localStorage.setItem('ai_model_url', modelUrl);
      localStorage.setItem('python_api_url', pythonApiUrl);
      localStorage.setItem('gemini_api_key', geminiKey);
      localStorage.setItem('ai_threshold', thresholdVal);
      
      aiThreshold = parseFloat(thresholdVal) / 100;
      
      const popover = document.getElementById('settings-popover');
      if (popover && typeof popover.hidePopover === 'function') {
        popover.hidePopover();
      }
      
      setupWebSocket();
      loadAIModel();
    });
  }

  // Không cần nút Chụp thủ công và Toggle auto-scan nữa
  // Chỉ dùng auto-scan mode

  // Global Start Game button event delegation
  document.addEventListener('click', (e) => {
    if (e.target && e.target.closest('#btn-start')) {
      sound.playWelcome();
      changeState('idle');
    }
  });
}

// Access Webcam
async function setupCamera() {
  const video = document.getElementById('webcam');
  const loadingPlaceholder = document.getElementById('camera-loading');
  const cameraContainer = document.querySelector('.camera-container');
  
  try {
    const stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: 'user', width: 640, height: 480 },
      audio: false
    });
    
    currentWebcamStream = stream;
    if (video) {
      video.srcObject = stream;
      video.onloadedmetadata = () => {
        video.play();
        if (loadingPlaceholder) loadingPlaceholder.hidden = true;
        if (cameraContainer) cameraContainer.classList.remove('has-error');
      };
    }
  } catch (error) {
    console.error("Camera access error:", error);
    if (loadingPlaceholder) {
      loadingPlaceholder.innerHTML = '<span>⚠️</span><p>Không truy cập được Camera.<br>Vui lòng cấp quyền!</p>';
    }
    if (cameraContainer) cameraContainer.classList.add('has-error');
  }
}

// Load AI Model (Python API, TF.js, Teachable Machine, Gemini, or MobileNet)
async function loadAIModel() {
  const statusDot = document.getElementById('ai-status-dot');
  const statusText = document.getElementById('ai-status-text');

  function setThreshold(val) {
    if (localStorage.getItem('ai_threshold')) return;
    aiThreshold = val / 100;
    const slider = document.getElementById('ai-threshold');
    const label = document.getElementById('threshold-val');
    if (slider) slider.value = val;
    if (label) label.innerText = `${val}%`;
  }

  function setStatus(tone, text) {
    if (statusDot) {
      statusDot.className = `status-dot active status-dot-${tone || 'accent'}`;
    }
    if (statusText) statusText.innerText = text;
  }

  try {
    isModelLoading = true;
    isScanningActive = false;
    isGeminiActive = false;
    if (statusDot) statusDot.className = 'status-dot';
    if (statusText) statusText.innerText = 'Đang tải mô hình AI...';

    const engine = await loadConfiguredAIEngine();
    model = engine.model;
    isCustomModel = engine.isCustomModel;
    isGeminiActive = engine.isGeminiActive;
    isModelLoading = false;
    setThreshold(engine.thresholdPercent);
    setStatus(engine.status.tone, engine.status.text);

    isScanningActive = true;
    predictLoop();
  } catch (err) {
    console.error('[AI] Load error:', err);
    if (statusDot) statusDot.className = 'status-dot';
    if (statusText) statusText.innerText = 'Không tải được AI';
    updateHUDStatus('Lỗi mô hình', '--');
  }
}

function updateAutoScanBtnUI() {
  const btn = document.getElementById('btn-toggle-auto');
  if (!btn) return;
  if (isAutoScanEnabled) {
    btn.innerHTML = '<span>🤖</span> Tự động: BẬT';
    btn.classList.add('is-active');
  } else {
    btn.innerHTML = '<span>✋</span> Tự động: TẮT';
    btn.classList.remove('is-active');
  }
}

// Helper to update the live overlay HUD status
function updateHUDStatus(statusText, predictionText) {
  const hudStatus = document.getElementById('hud-status');
  const hudPrediction = document.getElementById('hud-prediction');
  if (hudStatus) hudStatus.innerHTML = statusText;
  if (hudPrediction) hudPrediction.innerText = predictionText;
}

function resetPredictionHistory() {
  predictionHistory = [];
  lastPredictedItem = null;
}

function smoothPrediction(rawPrediction) {
  if (!rawPrediction || !rawPrediction.item) {
    resetPredictionHistory();
    return { item: null, confidence: 0, displayLabel: rawPrediction?.displayLabel || 'Khong thay gi...', stable: false };
  }

  predictionHistory.push(rawPrediction);
  if (predictionHistory.length > PREDICTION_WINDOW) predictionHistory.shift();

  const votes = new Map();
  predictionHistory.forEach(pred => {
    if (!pred.item) return;
    const current = votes.get(pred.item.id) || { count: 0, confidenceSum: 0, latest: pred };
    current.count += 1;
    current.confidenceSum += pred.confidence || 0;
    current.latest = pred;
    votes.set(pred.item.id, current);
  });

  let bestVote = null;
  votes.forEach(vote => {
    if (!bestVote || vote.count > bestVote.count || (vote.count === bestVote.count && vote.confidenceSum > bestVote.confidenceSum)) {
      bestVote = vote;
    }
  });

  if (!bestVote || bestVote.count < MIN_STABLE_VOTES) {
    return {
      item: null,
      confidence: rawPrediction.confidence || 0,
      displayLabel: rawPrediction.displayLabel || 'Dang kiem tra...',
      stable: false
    };
  }

  return {
    item: bestVote.latest.item,
    confidence: bestVote.confidenceSum / bestVote.count,
    displayLabel: bestVote.latest.displayLabel,
    stable: true
  };
}

async function predictLoop() {
  const video = document.getElementById('webcam');
  const camContainer = document.querySelector('.camera-container');

  // Không chạy nếu model chưa load hoặc đang ở state không phải idle
  if (!isScanningActive || isModelLoading || (!model && !isGeminiActive) || !video || video.readyState !== 4) {
    if (camContainer) camContainer.classList.remove('scanning');
    updateHUDStatus('⏸️ Tạm ngưng', '--');
    setTimeout(predictLoop, 500);
    return;
  }

  if (appState !== 'idle') {
    if (camContainer) camContainer.classList.remove('scanning');
    updateHUDStatus('⏸️ Tạm nghỉ', currentItem ? `${currentItem.emoji} ${currentItem.name}` : '--');
    autoScanCandidateId = null;
    resetPredictionHistory();
    setTimeout(predictLoop, 500);
    return;
  }

  console.log('[predictLoop] Running... State:', appState, 'Model:', model?._isPythonAPI ? 'Python API' : (isGeminiActive ? 'Gemini' : 'Other'));

  if (camContainer) camContainer.classList.add('scanning');

  // ── Chạy AI inference ──────────────────────────────────────────────────
  let matchedItem = null;
  let highestProb = 0;
  let displayLabel = 'Không thấy gì...';
  let rawPrediction = null;

  try {
    const targetCanvas = getCroppedCanvas(video);

    if (isGeminiActive) {
      // ── Gemini Vision API (giới hạn tần suất để tiết kiệm quota) ─────
      const now = Date.now();
      const timeSinceLastGeminiCall = now - (window._lastGeminiCallTime || 0);
      
      if (timeSinceLastGeminiCall >= 2000) {
        window._lastGeminiCallTime = now;
        
        const base64Img = targetCanvas.toDataURL('image/jpeg', 0.8).split(',')[1];
        const result = await callGeminiVision(base64Img);
        
        if (result && result.matchedId && result.matchedId !== 'none' && result.confidence >= aiThreshold) {
          matchedItem = trashItems.find(item => item.id === result.matchedId);
          highestProb = result.confidence;
          displayLabel = matchedItem
            ? `${matchedItem.emoji} ${matchedItem.name} (${Math.round(highestProb * 100)}%)`
            : `${result.matchedId} (${Math.round(highestProb * 100)}%)`;
          rawPrediction = { item: matchedItem, confidence: highestProb, displayLabel };
        }
      }

    } else if (model._isPythonAPI) {
      // ── Python Flask API ─────────────────────────────────────────────
      const now = Date.now();
      if (now - (window._lastPythonApiCallTime || 0) < API_PREVIEW_MS) {
        setTimeout(predictLoop, AUTO_PREVIEW_MS);
        return;
      }
      window._lastPythonApiCallTime = now;

      const base64Img = targetCanvas.toDataURL('image/jpeg', 0.8).split(',')[1];
      
      const response = await fetch(`${model._apiUrl}/predict`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ image: base64Img }),
        signal: AbortSignal.timeout(5000)
      });
      
      if (response.ok) {
        const result = await response.json();
        highestProb = result.confidence || 0;
        const secondProb = result.top_predictions?.[1]?.confidence || 0;
        const trustedHeuristics = ['red_soda_can', 'white_paper_scrap'];
        const hasTrustedHeuristic = trustedHeuristics.includes(result.heuristic);
        const confidentEnough = highestProb >= aiThreshold
          && (hasTrustedHeuristic || (highestProb - secondProb) >= MIN_CONF_MARGIN);
        
        if (confidentEnough) {
          matchedItem = trashItems.find(item => item.id === result.class);
          displayLabel = matchedItem
            ? `${matchedItem.emoji} ${matchedItem.name} (${Math.round(highestProb * 100)}%)`
            : `${result.class} (${Math.round(highestProb * 100)}%)`;
          rawPrediction = { item: matchedItem, confidence: highestProb, displayLabel };
        } else if (highestProb > 0.10) {
          displayLabel = `${result.class} (${Math.round(highestProb * 100)}%)`;
          console.log('[Python API] Prediction held by confidence gate:', {
            class: result.class,
            confidence: highestProb,
            second: secondProb,
            margin: highestProb - secondProb,
            heuristic: result.heuristic || null
          });
        }
      }

    } else if (isCustomModel && model._localLabels) {
      // ── Local TF.js model (train_dl_model.py) ──────────────────────────
      let probabilities;

      try {
        const inputTensor = tf.browser.fromPixels(targetCanvas)
          .resizeBilinear([224, 224])
          .toFloat()
          .expandDims(0);

        const outputTensor = model._isGraphModel
          ? model.execute(inputTensor)
          : model.predict(inputTensor);

        probabilities = await outputTensor.data();
        inputTensor.dispose();
        outputTensor.dispose();
      } catch (inferErr) {
        console.warn('[AI] Inference error:', inferErr.message);
        setTimeout(predictLoop, AUTO_PREVIEW_MS);
        return;
      }

      // Lấy class có xác suất cao nhất
      const { bestIdx: maxIdx, bestProb, margin } = getTopScores(probabilities);
      highestProb = bestProb;
      const predictedLabel = model._localLabels[maxIdx] || '';

      if (highestProb >= aiThreshold && margin >= MIN_CONF_MARGIN) {
        matchedItem = findTrashItemByLabel(predictedLabel);
      }
      if (highestProb > 0.10) {
        displayLabel = matchedItem
          ? `${matchedItem.emoji} ${matchedItem.name} (${Math.round(highestProb * 100)}%)`
          : `${predictedLabel} (${Math.round(highestProb * 100)}%)`;
      }
      if (matchedItem) rawPrediction = { item: matchedItem, confidence: highestProb, displayLabel };

    } else if (isCustomModel) {
      // ── Teachable Machine model ─────────────────────────────────────────
      const predictions = await model.predict(targetCanvas);
      if (predictions && predictions.length > 0) {
        predictions.sort((a, b) => b.probability - a.probability);
        const top = predictions[0];
        const second = predictions[1];
        highestProb = top.probability;
        if (highestProb >= aiThreshold && (!second || highestProb - second.probability >= MIN_CONF_MARGIN)) {
          matchedItem = findTrashItemByLabel(top.className);
        }
        if (highestProb > 0.12) {
          displayLabel = matchedItem
            ? `${matchedItem.emoji} ${matchedItem.name} (${Math.round(highestProb * 100)}%)`
            : `${top.className.split(',')[0]} (${Math.round(highestProb * 100)}%)`;
        }
        if (matchedItem) rawPrediction = { item: matchedItem, confidence: highestProb, displayLabel };
      }
    } else {
      // ── MobileNet fallback ──────────────────────────────────────────────
      const predictions = await model.classify(targetCanvas);
      if (predictions && predictions.length > 0) {
        const top = predictions[0];
        const second = predictions[1];
        highestProb = top.probability;
        if (highestProb >= aiThreshold && (!second || highestProb - second.probability >= MIN_CONF_MARGIN)) {
          const label = top.className.toLowerCase();
          matchedItem = trashItems.find(item =>
            item.keywords.some(kw => label.includes(kw))
          );
        }
        if (highestProb > 0.12) {
          displayLabel = matchedItem
            ? `${matchedItem.emoji} ${matchedItem.name} (${Math.round(highestProb * 100)}%)`
            : `${top.className.split(',')[0]} (${Math.round(highestProb * 100)}%)`;
        }
        if (matchedItem) rawPrediction = { item: matchedItem, confidence: highestProb, displayLabel };
      }
    }

    const stablePrediction = smoothPrediction(rawPrediction || { item: null, confidence: highestProb, displayLabel });
    matchedItem = stablePrediction.item;
    highestProb = stablePrediction.confidence || highestProb;
    displayLabel = stablePrediction.displayLabel || displayLabel;
    lastPredictedItem = matchedItem;

    // ── Auto-confirm logic ──────────────────────────────────────────────
    const now = Date.now();
    const inCooldown = now < autoScanCooldownUntil;

    if (!inCooldown && isAutoScanEnabled && matchedItem) {
      if (matchedItem.id === autoScanCandidateId) {
        // Cùng vật thể đang được giữ → tính thời gian
        const heldMs = now - autoScanCandidateSince;
        const remaining = Math.max(0, AUTO_CONFIRM_MS - heldMs);
        const progress = Math.min(100, Math.round((heldMs / AUTO_CONFIRM_MS) * 100));

        if (heldMs >= AUTO_CONFIRM_MS) {
          // ✅ Đủ thời gian ổn định → tự động kích hoạt!
          console.log('[Auto-scan] ✅ TRIGGER! Item:', matchedItem.name, 'State:', appState, 'Prob:', highestProb);
          
          // Chụp ảnh freeze frame
          const capturedImageData = targetCanvas.toDataURL('image/jpeg', 0.9);
          
          autoScanCandidateId = null;
          autoScanCooldownUntil = now + AUTO_COOLDOWN_MS;
          updateHUDStatus('🎯 Đã nhận diện!', `${matchedItem.emoji} ${matchedItem.name}`);
          updateConfirmProgressBar(0);
          sound.playScan();
          
          // Trigger scan với ảnh đã chụp
          triggerTrashScan(matchedItem, capturedImageData);
        } else {
          // Đang đếm ngược...
          if (progress % 20 === 0) {
            console.log('[Auto-scan] Counting...', Math.ceil(remaining/1000), 's remaining, progress:', progress, '%');
          }
          updateHUDStatus(
            `⏳ Giữ yên... ${Math.ceil(remaining / 1000)}s`,
            `${displayLabel} [${progress}%]`
          );
          updateConfirmProgressBar(progress);
        }
      } else {
        // Vật thể mới → reset timer
        console.log('[Auto-scan] 🔄 New item detected:', matchedItem.name, 'Starting timer...');
        autoScanCandidateId = matchedItem.id;
        autoScanCandidateSince = now;
        updateHUDStatus('👀 Đang nhận diện...', displayLabel);
        updateConfirmProgressBar(0);
      }
    } else if (inCooldown) {
      const waitSec = Math.ceil((autoScanCooldownUntil - now) / 1000);
      updateHUDStatus(`✅ Đã quét! Chờ ${waitSec}s...`, displayLabel || '--');
      updateConfirmProgressBar(0);
      autoScanCandidateId = null;
    } else if (!matchedItem) {
      // Không thấy vật thể → reset
      autoScanCandidateId = null;
      updateConfirmProgressBar(0);
      if (isAutoScanEnabled) {
        updateHUDStatus('🤖 Đưa rác vào khung...', displayLabel);
      } else {
        updateHUDStatus('🤖 Xem trước...', displayLabel);
      }
    } else if (!isAutoScanEnabled) {
      updateHUDStatus('🤖 Xem trước...', displayLabel);
    }

  } catch (e) {
    console.warn("AI frame skip:", e);
  }

  setTimeout(predictLoop, AUTO_PREVIEW_MS);
}

// Cập nhật thanh progress bar xác nhận auto-scan
function updateConfirmProgressBar(percent) {
  const bar = document.getElementById('auto-confirm-bar');
  if (!bar) return;
  bar.style.transform = `scaleX(${Math.max(0, Math.min(100, percent)) / 100})`;
  bar.style.opacity = percent > 0 ? '1' : '0';
  bar.className = percent > 70
    ? 'progress-success'
    : percent > 40
      ? 'progress-warning'
      : 'progress-accent';
}

// Execute manual capture & scan flow
async function executeManualScan() {
  if (appState !== 'idle') return;

  // Reset auto-scan state để tránh double-trigger
  autoScanCandidateId   = null;
  autoScanCooldownUntil = Date.now() + AUTO_COOLDOWN_MS;

  const btnCaptureScan = document.getElementById('btn-capture-scan');
  const video = document.getElementById('webcam');
  const camContainer = document.querySelector('.camera-container');

  if (!video || video.readyState !== 4) {
    updateHUDStatus('Camera chưa sẵn sàng', 'Hãy cấp quyền camera');
    if (camContainer) camContainer.classList.add('has-error');
    return;
  }

  try {
    // 1. Loading UI & Freeze Video Feed
    if (btnCaptureScan) {
      btnCaptureScan.disabled = true;
      btnCaptureScan.innerHTML = '<span>⏳</span> Đang quét...';
      btnCaptureScan.classList.add('is-loading');
    }
    
    // Freeze video to show captured snapshot
    video.pause();
    sound.playScan();
    updateHUDStatus('📸 Đang phân tích ảnh...', 'Đang xử lý...');

    // 2. Call AI
    let finalItem = null;

    if (model && model._isPythonAPI) {
      // ── Call Python Flask API ────────────────────────────────────────
      const base64Img = captureWebcamFrame();
      if (base64Img) {
        try {
          const response = await fetch(`${model._apiUrl}/predict`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ image: base64Img })
          });
          
          if (response.ok) {
            const result = await response.json();
            if (result.confidence >= aiThreshold) {
              finalItem = trashItems.find(item => item.id === result.class);
              console.log(`[Python API] ${result.class} (${Math.round(result.confidence*100)}%)`);
            }
          } else {
            throw new Error(`HTTP ${response.status}`);
          }
        } catch (apiErr) {
          console.error('[Python API] Error:', apiErr);
        }
      }

    } else if (isGeminiActive) {
      // Call Cloud Gemini API
      const base64Img = captureWebcamFrame();
      if (base64Img) {
        const result = await callGeminiVision(base64Img);
        if (result && result.matchedId && result.matchedId !== 'none' && result.confidence >= aiThreshold) {
          finalItem = trashItems.find(item => item.id === result.matchedId);
        }
      }
    } else {
      // Local model: use last predicted item in preview
      finalItem = lastPredictedItem;
    }

    // 3. Process AI Output
    if (finalItem) {
      console.log(`[Manual Scan] Nhận diện thành công: ${finalItem.name}`);
      updateHUDStatus('🎉 Nhận dạng thành công!', `${finalItem.emoji} ${finalItem.name}`);
      updateConfirmProgressBar(0);
      
      // Delay briefly to let user see "Success" HUD before transitioning
      setTimeout(() => {
        // Restore Video Playback
        video.play();
        if (btnCaptureScan) {
          btnCaptureScan.disabled = false;
          btnCaptureScan.innerHTML = '<span>📸</span> Chụp thủ công';
          btnCaptureScan.classList.remove('is-loading');
        }
        triggerTrashScan(finalItem);
      }, 800);

    } else {
      // No object recognized
      console.log("[Manual Scan] AI không nhận diện được vật thể nào.");
      updateHUDStatus('❌ Không nhận ra vật thể', 'Thử lại!');
      sound.playIncorrect();

      // Show notice in game screen content
      const screenContent = document.getElementById('screen-content');
      if (screenContent) {
        const oldContent = screenContent.innerHTML;
        screenContent.innerHTML = `
          <span class="huge-emoji">🧐</span>
          <h2 class="screen-title error-title">AI chưa nhận ra vật này!</h2>
          <p class="screen-desc">Bé hãy đặt vật rác ở chính giữa camera, giữ yên tay và chụp lại nhé!</p>
        `;
        
        setTimeout(() => {
          if (appState === 'idle') screenContent.innerHTML = oldContent;
        }, 3000);
      }

      // Restore camera & button state
      setTimeout(() => {
        video.play();
        if (btnCaptureScan) {
          btnCaptureScan.disabled = false;
          btnCaptureScan.innerHTML = '<span>📸</span> Chụp thủ công';
          btnCaptureScan.classList.remove('is-loading');
        }
      }, 1000);
    }

  } catch (err) {
    console.error("Manual scan error:", err);
    updateConfirmProgressBar(0);
    video.play();
    if (btnCaptureScan) {
      btnCaptureScan.disabled = false;
      btnCaptureScan.innerHTML = '<span>📸</span> Chụp thủ công';
      btnCaptureScan.classList.remove('is-loading');
    }
  }
}

function setupWebSocket() {
  setupHardwareConnection({
    onScanItem: triggerTrashScan,
    onSelectCategory: handleSelectedCategory
  });
}

// Triggered when an item is scanned
function triggerTrashScan(item, capturedImage = null) {
  console.log('[triggerTrashScan] Called with item:', item?.name, 'Current state:', appState, 'Has image:', !!capturedImage);
  
  if (!item) {
    console.warn('[triggerTrashScan] No item provided!');
    return;
  }
  
  if (appState === 'idle' || appState === 'instructing') {
    resetPredictionHistory();
    autoScanCandidateId = null;
    currentItem = item;
    
    // Lưu ảnh đã chụp để hiển thị trên màn hình kết quả
    currentItem._capturedImage = capturedImage;
    
    console.log('[triggerTrashScan] Changing state to instructing');
    changeState('instructing');
  } else {
    console.warn('[triggerTrashScan] Wrong state, cannot trigger. Current state:', appState);
  }
}

// Triggered when a bin selection is made
function handleSelectedCategory(selectedCategory) {
  if (appState !== 'instructing' || !currentItem) return;

  scoreTotal++;
  if (currentItem.category === selectedCategory) {
    scoreCorrect++;
    sound.playCorrect();
    changeState('correct');
  } else {
    sound.playIncorrect();
    changeState('incorrect');
  }
  updateScoreUI();
}

// Update Score Dashboard
function updateScoreUI() {
  const scoreCorrectEl = document.getElementById('score-correct');
  const scoreTotalEl = document.getElementById('score-total');
  
  if (scoreCorrectEl) scoreCorrectEl.innerText = scoreCorrect;
  if (scoreTotalEl) scoreTotalEl.innerText = scoreTotal;
}

function resetScore() {
  scoreCorrect = 0;
  scoreTotal = 0;
  updateScoreUI();
}

function resetGame() {
  resetScore();
  changeState('idle');
}

// Change application state and update UI
function changeState(newState) {
  appState = newState;
  const screenContent = document.getElementById('screen-content');
  if (!screenContent) return;

  if (confettiEffect) confettiEffect.stop();

  if (newState === 'idle') {
    currentItem = null;
    screenContent.innerHTML = `
      <div class="scanning-ring">
        <span class="huge-emoji scanning-emoji">👀</span>
      </div>
      <h2 class="screen-title waiting-title">Đang đợi các bé...</h2>
      <p class="screen-desc">Bé hãy quét thẻ mô hình rác hoặc đưa rác thật trước Camera để bắt đầu phân loại nhé!</p>
    `;
  } 
  
  else if (newState === 'instructing') {
    // Tạo HTML với hoặc không có ảnh đã chụp
    const capturedImageHTML = currentItem._capturedImage 
      ? `<div class="captured-frame captured-frame-primary">
           <img src="${currentItem._capturedImage}" alt="Ảnh đã chụp">
         </div>`
      : '';
    
    screenContent.innerHTML = `
      <span class="huge-emoji">${currentItem.emoji}</span>
      <h2 class="screen-title">Bé nhận biết được: ${currentItem.name}!</h2>
      ${capturedImageHTML}
      <p class="screen-desc">Bé hãy bấm nút chọn chiếc thùng rác có màu phù hợp nhé!</p>
      
      <div class="buttons-group">
        <button class="kids-btn btn-green" data-color="green">
          <span class="btn-emoji">♻️</span>
          Hữu cơ & Tái chế
        </button>
        <button class="kids-btn btn-yellow" data-color="yellow">
          <span class="btn-emoji">🗑️</span>
          Rác còn lại
        </button>
        <button class="kids-btn btn-red" data-color="red">
          <span class="btn-emoji">⚠️</span>
          Rác nguy hại
        </button>
      </div>
      <button id="btn-rescan" class="btn-small rescan-btn">Quét lại</button>
    `;

    const buttons = screenContent.querySelectorAll('.kids-btn');
    buttons.forEach(btn => {
      btn.addEventListener('click', () => {
        handleSelectedCategory(btn.getAttribute('data-color'));
      });
    });

    const btnRescan = screenContent.querySelector('#btn-rescan');
    if (btnRescan) {
      btnRescan.addEventListener('click', () => {
        resetPredictionHistory();
        autoScanCandidateId = null;
        autoScanCooldownUntil = Date.now() + 500;
        changeState('idle');
      });
    }
  } 
  
  else if (newState === 'correct') {
    const capturedImageHTML = currentItem._capturedImage 
      ? `<div class="captured-frame captured-frame-green">
           <img src="${currentItem._capturedImage}" alt="Ảnh đã chụp">
         </div>`
      : '';
      
    screenContent.innerHTML = `
      <span class="huge-emoji">🏆</span>
      <h2 class="screen-title success-title">Bé chọn chính xác!</h2>
      ${capturedImageHTML}
      <p class="screen-desc result-summary">Bạn thật là tuyệt vời! Món rác <b>${currentItem.emoji} ${currentItem.name}</b> đã được bỏ đúng chỗ! 🎉</p>
      
      <!-- Educational Info Panel -->
      <div class="lesson-panel">
        <h4>💡 Bài học cho bé:</h4>
        <p>${currentItem.tip || ''}</p>
        <h4>🌍 Tác động môi trường:</h4>
        <p>${currentItem.impact || ''}</p>
      </div>
    `;
    
    if (confettiEffect) confettiEffect.start();

    setTimeout(() => {
      if (appState === 'correct') changeState('idle');
    }, 4500);
  } 
  
  else if (newState === 'incorrect') {
    const capturedImageHTML = currentItem._capturedImage 
      ? `<div class="captured-frame captured-frame-red">
           <img src="${currentItem._capturedImage}" alt="Ảnh đã chụp">
         </div>`
      : '';
      
    screenContent.innerHTML = `
      <span class="huge-emoji">💫</span>
      <h2 class="screen-title error-title">Chưa đúng rồi bé ơi!</h2>
      ${capturedImageHTML}
      <p class="screen-desc">Đừng lo lắng nhé, hãy suy nghĩ lại một chút và nhấn lại nút chọn để thử lại xem nào! 💪</p>
    `;

    setTimeout(() => {
      if (appState === 'incorrect') changeState('instructing');
    }, 3500);
  }
}
