import { trashItems } from './mockData.js';
import { sound } from './sound.js';

// Application State
let appState = 'welcome'; // welcome, idle, instructing, correct, incorrect
let currentItem = null;
let scoreCorrect = 0;
let scoreTotal = 0;
let model = null;
let isCustomModel = false;
let isModelLoading = true;
let isScanningActive = false;
let socket = null;
let reconnectInterval = null;
let currentWebcamStream = null;

// AI Smoothing & Threshold parameters
let aiThreshold = 0.35;
let lastPredictedItem = null; // Vật thể đang nhìn thấy hiện tại

// Gemini API status
let isGeminiActive = false;

// ── Auto-scan state machine ──────────────────────────────────────────────────
// Cơ chế: AI phải nhìn thấy cùng 1 vật thể ổn định trong AUTO_CONFIRM_MS ms
// trước khi tự động kích hoạt scan → tránh nhận diện nhầm khi bé đưa tay qua
const AUTO_CONFIRM_MS   = 200;   // Thời gian giữ ổn định để xác nhận (0.2 giây - tối ưu cho vật nhỏ)
const AUTO_COOLDOWN_MS  = 1500;  // Thời gian chờ sau mỗi lần scan thành công (1.5s)
const AUTO_PREVIEW_MS   = 150;   // Tần suất chạy vòng lặp preview (ms - tăng tốc độ phản hồi)

let autoScanCandidateId  = null;  // ID của vật thể đang được "chờ xác nhận"
let autoScanCandidateSince = 0;   // Timestamp bắt đầu nhìn thấy vật thể đó
let autoScanCooldownUntil  = 0;   // Timestamp kết thúc cooldown
let isAutoScanEnabled      = true; // Luôn bật tự động (không có toggle nữa)

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
  setupCamera();
  loadAIModel();
  setupWebSocket();
  setupSimulationPanel();
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

  // Bind simulation controls reset
  const btnReset = document.getElementById('btn-sim-reset');
  if (btnReset) {
    btnReset.addEventListener('click', () => {
      scoreCorrect = 0;
      scoreTotal = 0;
      updateScoreUI();
    });
  }

  // Không cần nút Chụp thủ công và Toggle auto-scan nữa
  // Chỉ dùng auto-scan mode

  // Global Start Game button event delegation
  document.addEventListener('click', (e) => {
    if (e.target && e.target.id === 'btn-start') {
      sound.playWelcome();
      changeState('idle');
    }
  });
}

// Access Webcam
async function setupCamera() {
  const video = document.getElementById('webcam');
  const loadingPlaceholder = document.getElementById('camera-loading');
  
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
        if (loadingPlaceholder) loadingPlaceholder.style.display = 'none';
      };
    }
  } catch (error) {
    console.error("Camera access error:", error);
    if (loadingPlaceholder) {
      loadingPlaceholder.innerHTML = '<span>⚠️</span><p>Không truy cập được Camera.<br>Vui lòng cấp quyền!</p>';
    }
  }
}

// Load AI Model (MobileNet or custom Teachable Machine)
async function loadAIModel() {
  const statusDot  = document.getElementById('ai-status-dot');
  const statusText = document.getElementById('ai-status-text');

  // Đọc cấu hình đã lưu
  const savedModelUrl = localStorage.getItem('ai_model_url') || '';
  const geminiKey     = localStorage.getItem('gemini_api_key') || '';
  const pythonApiUrl  = localStorage.getItem('python_api_url') || 'http://localhost:5000';

  // Model local mặc định (sau khi chạy train_dl_model.py)
  const LOCAL_MODEL_URL = '/tfjs_model/model.json';

  function setThreshold(val) {
    if (localStorage.getItem('ai_threshold')) return; // giữ nguyên nếu user đã tự chỉnh
    aiThreshold = val / 100;
    const slider = document.getElementById('ai-threshold');
    const label  = document.getElementById('threshold-val');
    if (slider) slider.value = val;
    if (label)  label.innerText = `${val}%`;
  }

  function setStatus(color, shadow, text) {
    if (statusDot) {
      statusDot.className = 'status-dot active';
      statusDot.style.background  = color;
      statusDot.style.boxShadow   = `0 0 10px ${shadow || color}`;
    }
    if (statusText) statusText.innerText = text;
  }

  try {
    isModelLoading  = true;
    isScanningActive = false;
    isGeminiActive  = false;
    if (statusDot)  statusDot.className = 'status-dot';
    if (statusText) statusText.innerText = 'Đang tải mô hình AI...';

    // ── Kiểm tra Python API server có sẵn không ──────────────────────────
    let pythonApiAvailable = false;
    try {
      const healthRes = await fetch(`${pythonApiUrl}/health`, {
        method: 'GET',
        signal: AbortSignal.timeout(2000) // 2s timeout
      });
      if (healthRes.ok) {
        const healthData = await healthRes.json();
        if (healthData.status === 'ok') {
          pythonApiAvailable = true;
          console.log('[AI] Python API server available:', pythonApiUrl);
        }
      }
    } catch (err) {
      console.log('[AI] Python API not available:', err.message);
    }

    // ── Thứ tự ưu tiên: Python API > Teachable Machine > Gemini > MobileNet ──
    if (pythonApiAvailable) {
      // ── Python Flask API (sử dụng model .h5 trực tiếp) ──────────────
      model = { _isPythonAPI: true, _apiUrl: pythonApiUrl };
      isCustomModel = true;
      isModelLoading = false;
      setThreshold(45); // Giảm từ 55% → 45% để nhận diện vật nhỏ tốt hơn
      setStatus('var(--color-green)', null, '🐍 Python AI API');
      isScanningActive = true;
      predictLoop();
      return;

    } else if (savedModelUrl && !savedModelUrl.endsWith('.json')) {
      // ── B. Teachable Machine URL ───────────────────────────────────────
      console.log('[AI] Loading Teachable Machine model:', savedModelUrl);
      if (typeof tmImage === 'undefined') throw new Error('Thiếu thư viện Teachable Machine');

      const base = savedModelUrl.endsWith('/') ? savedModelUrl : savedModelUrl + '/';
      model = await tmImage.load(base + 'model.json', base + 'metadata.json');
      isCustomModel = true;
      isModelLoading = false;
      setThreshold(75);
      setStatus('var(--color-green)', null, '🎓 Teachable Machine sẵn sàng');

    } else if (geminiKey) {
      // ── C. Gemini Vision (không có model local) ────────────────────────
      console.log('[AI] Using Gemini Vision API');
      isGeminiActive  = true;
      isCustomModel   = false;
      isModelLoading  = false;
      setThreshold(75);
      if (statusDot) {
        statusDot.className = 'status-dot active';
        statusDot.style.background = 'linear-gradient(135deg, #f59e0b, #ec4899)';
        statusDot.style.boxShadow  = '0 0 12px #ec4899';
      }
      if (statusText) statusText.innerText = '✨ Gemini Vision';
      isScanningActive = true;
      predictLoop();
      return;

    } else {
      // ── D. MobileNet fallback ──────────────────────────────────────────
      console.log('[AI] Loading MobileNet fallback');
      if (typeof mobilenet === 'undefined') throw new Error('Thiếu thư viện MobileNet');

      model = await mobilenet.load();
      isCustomModel = false;
      isModelLoading = false;
      setThreshold(35);
      setStatus('var(--color-primary)', null, '🔍 AI Mặc định (MobileNet)');
    }

    isScanningActive = true;
    predictLoop();

  } catch (err) {
    console.error('[AI] Load error:', err);
    if (statusDot)  statusDot.className = 'status-dot';
    if (statusText) statusText.innerText = '⚠️ Lỗi tải AI';
    updateHUDStatus('⚠️ Lỗi mô hình', '--');
  }
}

// Cập nhật UI nút toggle auto-scan
function updateAutoScanBtnUI() {
  const btn = document.getElementById('btn-toggle-auto');
  if (!btn) return;
  if (isAutoScanEnabled) {
    btn.innerHTML = '<span>🤖</span> Tự động: BẬT';
    btn.style.background = 'var(--color-green)';
    btn.style.color = 'white';
  } else {
    btn.innerHTML = '<span>✋</span> Tự động: TẮT';
    btn.style.background = 'oklch(0.55 0.02 240)';
    btn.style.color = 'white';
  }
}

// Helper to update the live overlay HUD status
function updateHUDStatus(statusText, predictionText) {
  const hudStatus = document.getElementById('hud-status');
  const hudPrediction = document.getElementById('hud-prediction');
  if (hudStatus) hudStatus.innerHTML = statusText;
  if (hudPrediction) hudPrediction.innerText = predictionText;
}

// Global offscreen canvas for high-performance cropping
let offscreenCanvas = null;

function getCroppedCanvas(video) {
  if (!offscreenCanvas) {
    offscreenCanvas = document.createElement('canvas');
    offscreenCanvas.width = 300; // Optimal resolution for AI
    offscreenCanvas.height = 300;
  }
  const ctx = offscreenCanvas.getContext('2d', { willReadFrequently: true });
  const vw = video.videoWidth;
  const vh = video.videoHeight;
  
  // Crop the central 60% of the video to match the Bounding Box in UI
  const cw = vw * 0.6;
  const ch = vh * 0.6;
  const cx = (vw - cw) / 2;
  const cy = (vh - ch) / 2;
  
  // drawImage(image, sx, sy, sWidth, sHeight, dx, dy, dWidth, dHeight)
  ctx.drawImage(video, cx, cy, cw, ch, 0, 0, offscreenCanvas.width, offscreenCanvas.height);
  return offscreenCanvas;
}

// Helper to capture a compressed frame from the webcam (Cropped)
function captureWebcamFrame() {
  const video = document.getElementById('webcam');
  if (!video || video.readyState !== 4) return null;
  
  const canvas = getCroppedCanvas(video);
  const dataUrl = canvas.toDataURL('image/jpeg', 0.8); 
  return dataUrl.split(',')[1]; 
}

// Helper to clean markdown blocks from LLM JSON responses
function cleanJSONString(str) {
  let cleaned = str.trim();
  if (cleaned.startsWith('```')) {
    cleaned = cleaned.replace(/^```(?:json)?\n?/i, '');
    cleaned = cleaned.replace(/\n?```$/i, '');
  }
  return cleaned.trim();
}

// Call Google Gemini 1.5 Flash Vision API
async function callGeminiVision(base64Image) {
  const key = localStorage.getItem('gemini_api_key');
  if (!key) {
    console.warn("Chưa cấu hình Gemini API Key.");
    return null;
  }

  const url = `https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=${key}`;
  const dbIds = trashItems.map(item => item.id).join(', ');

  const promptText = `
    You are the AI engine for a kids trash sorting station.
    Look at this image. Identify the primary waste object held by the user in front of the camera.
    Match it to one of these database IDs: [${dbIds}].
    If no object is held or if you see only background/a person, return "none".
    Respond ONLY in strict JSON format:
    {"matchedId": "id_here_or_none", "confidence": 0.95}
  `;

  const payload = {
    contents: [
      {
        parts: [
          { text: promptText },
          {
            inlineData: {
              mimeType: 'image/jpeg',
              data: base64Image
            }
          }
        ]
      }
    ],
    generationConfig: {
      responseMimeType: 'application/json'
    }
  };

  try {
    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    
    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`HTTP error! status: ${response.status}, body: ${errorText}`);
    }
    
    const data = await response.json();
    if (!data.candidates || data.candidates.length === 0) {
      throw new Error("Gemini API returned empty candidates list.");
    }
    
    const responseText = data.candidates[0].content.parts[0].text;
    console.log("Raw Gemini API Response:", responseText);

    let matchedId = "none";
    let confidence = 0.0;

    try {
      const cleaned = cleanJSONString(responseText);
      const result = JSON.parse(cleaned);
      matchedId = result.matchedId || "none";
      confidence = result.confidence || 0.0;
    } catch (parseErr) {
      console.warn("JSON.parse failed. Retrying with regex extraction...", parseErr);
      // Fallback regex matching if JSON output contains extra markdown formatting
      const idMatch = responseText.match(/"matchedId"\s*:\s*"([^"]+)"/);
      const confMatch = responseText.match(/"confidence"\s*:\s*([0-9.]+)/);
      
      if (idMatch) matchedId = idMatch[1];
      if (confMatch) confidence = parseFloat(confMatch[1]);
    }

    console.log(`Parsed Gemini result -> id: ${matchedId}, confidence: ${confidence}`);
    return { matchedId, confidence };

  } catch (err) {
    console.error("Gemini Vision API error details:", err);
    return null;
  }
}

// Vòng lặp AI liên tục: preview + auto-confirm khi phát hiện ổn định
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
    setTimeout(predictLoop, 500);
    return;
  }

  console.log('[predictLoop] Running... State:', appState, 'Model:', model?._isPythonAPI ? 'Python API' : (isGeminiActive ? 'Gemini' : 'Other'));

  if (camContainer) camContainer.classList.add('scanning');

  // ── Chạy AI inference ──────────────────────────────────────────────────
  let matchedItem = null;
  let highestProb = 0;
  let displayLabel = 'Không thấy gì...';

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
        }
      }

    } else if (model._isPythonAPI) {
      // ── Python Flask API ─────────────────────────────────────────────
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
        
        if (highestProb >= aiThreshold) {
          matchedItem = trashItems.find(item => item.id === result.class);
          displayLabel = matchedItem
            ? `${matchedItem.emoji} ${matchedItem.name} (${Math.round(highestProb * 100)}%)`
            : `${result.class} (${Math.round(highestProb * 100)}%)`;
        } else if (highestProb > 0.10) {
          displayLabel = `${result.class} (${Math.round(highestProb * 100)}%)`;
        }
      }

    } else if (isCustomModel && model._localLabels) {
      // ── Local TF.js model (train_dl_model.py) ──────────────────────────
      let probabilities;

      try {
        const inputTensor = tf.browser.fromPixels(targetImage)
          .resizeBilinear([224, 224])
          .toFloat()
          .div(255.0)
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
      let maxIdx = 0;
      for (let i = 1; i < probabilities.length; i++) {
        if (probabilities[i] > probabilities[maxIdx]) maxIdx = i;
      }
      highestProb = probabilities[maxIdx];
      const predictedLabel = model._localLabels[maxIdx] || '';

      if (highestProb >= aiThreshold) {
        matchedItem = trashItems.find(item => item.id === predictedLabel);
        if (!matchedItem) {
          matchedItem = trashItems.find(item =>
            item.keywords && item.keywords.some(kw => predictedLabel.includes(kw))
          );
        }
      }
      if (highestProb > 0.10) {
        displayLabel = matchedItem
          ? `${matchedItem.emoji} ${matchedItem.name} (${Math.round(highestProb * 100)}%)`
          : `${predictedLabel} (${Math.round(highestProb * 100)}%)`;
      }

    } else if (isCustomModel) {
      // ── Teachable Machine model ─────────────────────────────────────────
      const predictions = await model.predict(targetImage);
      if (predictions && predictions.length > 0) {
        predictions.sort((a, b) => b.probability - a.probability);
        const top = predictions[0];
        highestProb = top.probability;
        if (highestProb >= aiThreshold) {
          const className = top.className.toLowerCase().trim();
          matchedItem = trashItems.find(item =>
            item.id === className || item.name.toLowerCase() === className
          );
        }
        if (highestProb > 0.12) {
          displayLabel = matchedItem
            ? `${matchedItem.emoji} ${matchedItem.name} (${Math.round(highestProb * 100)}%)`
            : `${top.className.split(',')[0]} (${Math.round(highestProb * 100)}%)`;
        }
      }
    } else {
      // ── MobileNet fallback ──────────────────────────────────────────────
      const predictions = await model.classify(targetImage);
      if (predictions && predictions.length > 0) {
        const top = predictions[0];
        highestProb = top.probability;
        if (highestProb >= aiThreshold) {
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
      }
    }

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
  let bar = document.getElementById('auto-confirm-bar');
  if (!bar) return;
  bar.style.width = `${percent}%`;
  bar.style.opacity = percent > 0 ? '1' : '0';
  // Màu: xanh khi gần xong
  bar.style.background = percent > 70
    ? 'var(--color-green)'
    : percent > 40
      ? '#f59e0b'
      : 'var(--color-primary)';
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
    alert("Camera chưa sẵn sàng!");
    return;
  }

  try {
    // 1. Loading UI & Freeze Video Feed
    if (btnCaptureScan) {
      btnCaptureScan.disabled = true;
      btnCaptureScan.innerHTML = '<span>⏳</span> Đang quét...';
      btnCaptureScan.style.background = 'oklch(0.6 0.02 240)'; // Grayish loading
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
          btnCaptureScan.style.background = ''; // Restore style
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
          <h2 class="screen-title" style="color: var(--color-red);">AI chưa nhận ra vật này!</h2>
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
          btnCaptureScan.style.background = '';
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
      btnCaptureScan.style.background = '';
    }
  }
}

// Connect to ESP32 WebSocket
function setupWebSocket() {
  const statusDot = document.getElementById('esp-status-dot');
  const statusText = document.getElementById('esp-status-text');
  const ip = localStorage.getItem('esp32_ip');

  if (socket) {
    socket.close();
  }

  if (reconnectInterval) {
    clearInterval(reconnectInterval);
    reconnectInterval = null;
  }

  if (!ip) {
    if (statusDot) statusDot.className = 'status-dot';
    if (statusText) statusText.innerText = 'Chưa thiết lập IP';
    return;
  }

  if (statusDot) statusDot.className = 'status-dot';
  if (statusText) statusText.innerText = `Đang kết nối...`;

  try {
    socket = new WebSocket(`ws://${ip}:81`);
    
    // Timeout sau 3s nếu không connect được
    const connectTimeout = setTimeout(() => {
      if (socket && socket.readyState !== WebSocket.OPEN) {
        console.log('[WebSocket] Connection timeout, skipping auto-reconnect');
        socket.close();
        if (statusDot) statusDot.className = 'status-dot';
        if (statusText) statusText.innerText = 'Chưa kết nối (sẽ dùng sau)';
      }
    }, 3000);

    socket.onopen = () => {
      clearTimeout(connectTimeout);
      console.log(`WebSocket connected to ESP32: ${ip}`);
      if (statusDot) statusDot.className = 'status-dot active';
      if (statusText) statusText.innerText = 'Đã kết nối Trạm';
    };

    socket.onmessage = (event) => {
      handleHardwareMessage(event.data);
    };

    socket.onclose = () => {
      clearTimeout(connectTimeout);
      console.log("[WebSocket] Connection closed");
      if (statusDot) statusDot.className = 'status-dot';
      if (statusText) statusText.innerText = 'Chưa kết nối';
      
      // Không auto-reconnect để tránh spam errors
      // Uncomment dòng dưới khi đã có ESP32:
      // reconnectInterval = setTimeout(setupWebSocket, 5000);
    };

    socket.onerror = (error) => {
      clearTimeout(connectTimeout);
      console.log("[WebSocket] Connection failed (ESP32 chưa sẵn sàng)");
      // Không log error chi tiết để tránh spam console
    };
  } catch (err) {
    console.log("[WebSocket] Init failed:", err.message);
  }
}

// Handle real signals from ESP32 hardware
function handleHardwareMessage(data) {
  try {
    const msg = JSON.parse(data);
    console.log("Nhận tín hiệu phần cứng:", msg);

    if (msg.type === 'rfid') {
      const matched = trashItems.find(item => item.id === msg.itemId);
      if (matched) {
        triggerTrashScan(matched);
      }
    } else if (msg.type === 'button') {
      handleSelectedCategory(msg.color);
    }
  } catch (e) {
    console.warn("Tín hiệu phần cứng không hợp lệ:", data);
  }
}

// Triggered when an item is scanned
function triggerTrashScan(item, capturedImage = null) {
  console.log('[triggerTrashScan] Called with item:', item?.name, 'Current state:', appState, 'Has image:', !!capturedImage);
  
  if (!item) {
    console.warn('[triggerTrashScan] No item provided!');
    return;
  }
  
  if (appState === 'idle' || appState === 'instructing') {
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
        <span class="huge-emoji" style="position: absolute;">👀</span>
      </div>
      <h2 class="screen-title" style="margin-top: 1rem;">Đang đợi các bé...</h2>
      <p class="screen-desc">Bé hãy quét thẻ mô hình rác hoặc đưa rác thật trước Camera để bắt đầu phân loại nhé!</p>
    `;
  } 
  
  else if (newState === 'instructing') {
    // Tạo HTML với hoặc không có ảnh đã chụp
    const capturedImageHTML = currentItem._capturedImage 
      ? `<div style="margin: 0.5rem auto 1rem; max-width: 280px; border-radius: 16px; overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.15); border: 3px solid var(--color-primary);">
           <img src="${currentItem._capturedImage}" alt="Ảnh đã chụp" style="width: 100%; height: auto; display: block;">
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
    `;

    const buttons = screenContent.querySelectorAll('.kids-btn');
    buttons.forEach(btn => {
      btn.addEventListener('click', () => {
        handleSelectedCategory(btn.getAttribute('data-color'));
      });
    });
  } 
  
  else if (newState === 'correct') {
    const capturedImageHTML = currentItem._capturedImage 
      ? `<div style="margin: 0.5rem auto 1rem; max-width: 240px; border-radius: 16px; overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.15); border: 3px solid var(--color-green);">
           <img src="${currentItem._capturedImage}" alt="Ảnh đã chụp" style="width: 100%; height: auto; display: block;">
         </div>`
      : '';
      
    screenContent.innerHTML = `
      <span class="huge-emoji" style="animation: wiggling 1s infinite;">🏆</span>
      <h2 class="screen-title" style="color: var(--color-green); font-size: 2.3rem;">Bé chọn chính xác!</h2>
      ${capturedImageHTML}
      <p class="screen-desc" style="font-size: 1.2rem; font-weight: 600; margin-bottom: 0.5rem;">Bạn thật là tuyệt vời! Món rác <b>${currentItem.emoji} ${currentItem.name}</b> đã được bỏ đúng chỗ! 🎉</p>
      
      <!-- Educational Info Panel -->
      <div style="margin-top: 1rem; padding: 1.2rem; background: rgba(255,255,255,0.95); border-radius: 18px; border: 2px solid var(--color-green); max-width: 580px; box-shadow: 0 4px 20px rgba(0,0,0,0.06); text-align: left; animation: slideUp 0.4s ease;">
        <h4 style="color: var(--color-green); font-weight: 800; font-size: 1rem; margin-bottom: 0.3rem; display: flex; align-items: center; gap: 0.4rem;">💡 Bài học cho bé:</h4>
        <p style="font-size: 0.92rem; line-height: 1.4; color: #222; margin-bottom: 0.6rem;">${currentItem.tip || ''}</p>
        <h4 style="color: var(--color-primary); font-weight: 800; font-size: 1rem; margin-bottom: 0.3rem; display: flex; align-items: center; gap: 0.4rem;">🌍 Tác động môi trường:</h4>
        <p style="font-size: 0.92rem; line-height: 1.4; color: #444;">${currentItem.impact || ''}</p>
      </div>
    `;
    
    if (confettiEffect) confettiEffect.start();

    setTimeout(() => {
      if (appState === 'correct') changeState('idle');
    }, 4500);
  } 
  
  else if (newState === 'incorrect') {
    const capturedImageHTML = currentItem._capturedImage 
      ? `<div style="margin: 0.5rem auto 1rem; max-width: 240px; border-radius: 16px; overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.15); border: 3px solid var(--color-red);">
           <img src="${currentItem._capturedImage}" alt="Ảnh đã chụp" style="width: 100%; height: auto; display: block;">
         </div>`
      : '';
      
    screenContent.innerHTML = `
      <span class="huge-emoji">💫</span>
      <h2 class="screen-title" style="color: var(--color-red);">Chưa đúng rồi bé ơi!</h2>
      ${capturedImageHTML}
      <p class="screen-desc">Đừng lo lắng nhé, hãy suy nghĩ lại một chút và nhấn lại nút chọn để thử lại xem nào! 💪</p>
    `;

    setTimeout(() => {
      if (appState === 'incorrect') changeState('instructing');
    }, 3500);
  }
}

// Setup Developer Simulation Panel Controls
function setupSimulationPanel() {
  const btnToggleSim = document.getElementById('btn-toggle-sim');
  const simPanel = document.getElementById('sim-panel');
  const rfidListEl = document.getElementById('sim-rfid-list');

  if (btnToggleSim && simPanel) {
    btnToggleSim.addEventListener('click', () => {
      simPanel.classList.toggle('show');
    });
  }

  if (rfidListEl) {
    rfidListEl.innerHTML = '';
    trashItems.forEach(item => {
      const btn = document.createElement('button');
      btn.className = 'btn-sim-item';
      btn.innerText = item.emoji;
      btn.title = `Quét ${item.name}`;
      btn.addEventListener('click', () => {
        triggerTrashScan(item);
      });
      rfidListEl.appendChild(btn);
    });
  }

  const simGreen = document.getElementById('sim-btn-green');
  const simYellow = document.getElementById('sim-btn-yellow');
  const simRed = document.getElementById('sim-btn-red');

  if (simGreen) simGreen.addEventListener('click', () => handleSelectedCategory('green'));
  if (simYellow) simYellow.addEventListener('click', () => handleSelectedCategory('yellow'));
  if (simRed) simRed.addEventListener('click', () => handleSelectedCategory('red'));

  window.simulateRFID = (itemId) => {
    const matched = trashItems.find(item => item.id === itemId);
    if (matched) triggerTrashScan(matched);
  };
  window.simulateButton = (color) => handleSelectedCategory(color);
  window.resetGame = () => {
    scoreCorrect = 0;
    scoreTotal = 0;
    updateScoreUI();
    changeState('idle');
  };
}
