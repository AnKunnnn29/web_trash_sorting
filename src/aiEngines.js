import { sortableTrashItems } from './mockData.js';

const LOCAL_MODEL_URL = '/tfjs_model/model.json';
const ANALYSIS_SIZE = 224;
const PAPER_CANDIDATE_LABELS = new Set([
  'wipe', 'chewing_gum', 'newspaper', 'milk_carton', 'plastic_bag', 'diaper'
]);
const PAPER_BLOCKED_LABELS = new Set([
  'soda_can', 'bottle', 'glass_bottle', 'shampoo_bottle', 'aerosol'
]);

let analysisCanvas = null;

function getAnalysisImageData(sourceCanvas) {
  if (!analysisCanvas) {
    analysisCanvas = document.createElement('canvas');
    analysisCanvas.width = ANALYSIS_SIZE;
    analysisCanvas.height = ANALYSIS_SIZE;
  }

  const ctx = analysisCanvas.getContext('2d', { willReadFrequently: true });
  ctx.drawImage(sourceCanvas, 0, 0, ANALYSIS_SIZE, ANALYSIS_SIZE);
  return ctx.getImageData(0, 0, ANALYSIS_SIZE, ANALYSIS_SIZE);
}

function looksLikeRedSodaCan(pixels) {
  let redCount = 0;
  let minX = ANALYSIS_SIZE;
  let maxX = -1;
  let minY = ANALYSIS_SIZE;
  let maxY = -1;

  for (let y = 0; y < ANALYSIS_SIZE; y += 1) {
    for (let x = 0; x < ANALYSIS_SIZE; x += 1) {
      const offset = (y * ANALYSIS_SIZE + x) * 4;
      const r = pixels[offset];
      const g = pixels[offset + 1];
      const b = pixels[offset + 2];
      if (!(r > 90 && r > g * 1.25 && r > b * 1.15)) continue;

      redCount += 1;
      minX = Math.min(minX, x);
      maxX = Math.max(maxX, x);
      minY = Math.min(minY, y);
      maxY = Math.max(maxY, y);
    }
  }

  const redRatio = redCount / (ANALYSIS_SIZE * ANALYSIS_SIZE);
  if (redRatio < 0.035 || redCount === 0) return false;

  const width = maxX - minX + 1;
  const height = maxY - minY + 1;
  return height / Math.max(width, 1) >= 1.35 || redRatio >= 0.12;
}

function looksLikeWhitePaperScrap(pixels) {
  const totalPixels = ANALYSIS_SIZE * ANALYSIS_SIZE;
  const mask = new Uint8Array(totalPixels);
  let whiteCount = 0;

  for (let y = 0; y < ANALYSIS_SIZE; y += 1) {
    for (let x = 0; x < ANALYSIS_SIZE; x += 1) {
      const pixelIndex = y * ANALYSIS_SIZE + x;
      const offset = pixelIndex * 4;
      const r = pixels[offset];
      const g = pixels[offset + 1];
      const b = pixels[offset + 2];
      const brightness = (r + g + b) / 3;
      const saturation = Math.max(r, g, b) - Math.min(r, g, b);
      const inCenter = x > 28 && x < 196 && y > 24 && y < 200;
      const isWhite = inCenter && brightness > 145 && saturation < 58
        && r > 125 && g > 125 && b > 125;

      if (isWhite) {
        mask[pixelIndex] = 1;
        whiteCount += 1;
      }
    }
  }

  const whiteRatio = whiteCount / totalPixels;
  if (whiteRatio < 0.025 || whiteRatio > 0.45) return false;

  const visited = new Uint8Array(totalPixels);
  let largest = null;

  for (let start = 0; start < totalPixels; start += 1) {
    if (!mask[start] || visited[start]) continue;

    const queue = [start];
    visited[start] = 1;
    let cursor = 0;
    let count = 0;
    let minX = ANALYSIS_SIZE;
    let maxX = -1;
    let minY = ANALYSIS_SIZE;
    let maxY = -1;

    while (cursor < queue.length) {
      const current = queue[cursor];
      cursor += 1;
      const x = current % ANALYSIS_SIZE;
      const y = Math.floor(current / ANALYSIS_SIZE);
      count += 1;
      minX = Math.min(minX, x);
      maxX = Math.max(maxX, x);
      minY = Math.min(minY, y);
      maxY = Math.max(maxY, y);

      const neighbors = [];
      if (x > 0) neighbors.push(current - 1);
      if (x < ANALYSIS_SIZE - 1) neighbors.push(current + 1);
      if (y > 0) neighbors.push(current - ANALYSIS_SIZE);
      if (y < ANALYSIS_SIZE - 1) neighbors.push(current + ANALYSIS_SIZE);

      neighbors.forEach((neighbor) => {
        if (mask[neighbor] && !visited[neighbor]) {
          visited[neighbor] = 1;
          queue.push(neighbor);
        }
      });
    }

    if (!largest || count > largest.count) {
      largest = { count, minX, maxX, minY, maxY };
    }
  }

  if (!largest) return false;

  const width = largest.maxX - largest.minX + 1;
  const height = largest.maxY - largest.minY + 1;
  const componentRatio = largest.count / totalPixels;
  const bboxAreaRatio = (width * height) / totalPixels;
  const aspect = Math.max(width, height) / Math.max(Math.min(width, height), 1);

  return componentRatio >= 0.02
    && bboxAreaRatio >= 0.035
    && width >= 24
    && height >= 24
    && aspect <= 4;
}

export function applyPixelHeuristics(pixels, predictedLabel, confidence) {
  if (predictedLabel !== 'soda_can' && looksLikeRedSodaCan(pixels)) {
    return {
      label: 'soda_can',
      confidence: Math.min(0.98, Math.max(confidence + 0.02, 0.74)),
      heuristic: 'red_soda_can'
    };
  }

  if (
    !PAPER_BLOCKED_LABELS.has(predictedLabel)
    && (PAPER_CANDIDATE_LABELS.has(predictedLabel) || confidence < 0.55)
    && looksLikeWhitePaperScrap(pixels)
  ) {
    return {
      label: 'newspaper',
      confidence: Math.min(0.86, Math.max(confidence + 0.28, 0.62)),
      heuristic: 'white_paper_scrap'
    };
  }

  return { label: predictedLabel, confidence, heuristic: null };
}

export function applyVisionHeuristics(sourceCanvas, predictedLabel, confidence) {
  return applyPixelHeuristics(
    getAnalysisImageData(sourceCanvas).data,
    predictedLabel,
    confidence
  );
}

export function getTopScores(probabilities) {
  let bestIdx = -1;
  let bestProb = 0;
  let secondProb = 0;

  for (let i = 0; i < probabilities.length; i++) {
    const prob = Number(probabilities[i]) || 0;
    if (prob > bestProb) {
      secondProb = bestProb;
      bestProb = prob;
      bestIdx = i;
    } else if (prob > secondProb) {
      secondProb = prob;
    }
  }

  return { bestIdx, bestProb, secondProb, margin: bestProb - secondProb };
}

export function findTrashItemByLabel(label) {
  const normalized = String(label || '').toLowerCase().trim();
  if (!normalized) return null;

  return sortableTrashItems.find(item => item.id === normalized)
    || sortableTrashItems.find(item => item.name.toLowerCase() === normalized)
    || sortableTrashItems.find(item =>
      item.keywords && item.keywords.some(kw => normalized.includes(kw.toLowerCase()))
    )
    || null;
}

export async function loadConfiguredAIEngine(providerOverride = null) {
  const savedProvider = localStorage.getItem('ai_provider') === 'local' ? 'local' : 'qwen';
  const provider = providerOverride === 'local' ? 'local' : savedProvider;

  if (provider === 'qwen') {
    return {
      model: null,
      provider: 'qwen',
      isCustomModel: false,
      isQwenActive: true,
      thresholdPercent: 65,
      status: { tone: 'accent', text: '☁️ Qwen Vision sẵn sàng' }
    };
  }

  try {
    console.log('[AI] Loading bundled TFJS Graph Model...');
    const localModel = await tf.loadGraphModel(LOCAL_MODEL_URL);
    const labelsRes = await fetch('/tfjs_model/labels.json');
    if (!labelsRes.ok) throw new Error(`Could not load labels: HTTP ${labelsRes.status}`);
    localModel._localLabels = await labelsRes.json();
    localModel._isGraphModel = true;
    return {
      model: localModel,
      provider: 'local',
      isCustomModel: true,
      isQwenActive: false,
      thresholdPercent: 45,
      status: {
        tone: 'success',
        text: '⚡ AI trình duyệt sẵn sàng'
      }
    };
  } catch (localErr) {
    console.log('[AI] Bundled TFJS model failed:', localErr.message);
  }

  console.log('[AI] Loading MobileNet fallback');
  if (typeof mobilenet === 'undefined') throw new Error('Thiếu thư viện MobileNet');

  return {
    model: await mobilenet.load(),
    provider: 'local',
    isCustomModel: false,
    isQwenActive: false,
    thresholdPercent: 35,
    status: {
      tone: 'accent',
      text: '🔍 MobileNet sẵn sàng'
    }
  };
}

function cleanJSONString(str) {
  let cleaned = str.trim();
  if (cleaned.startsWith('```')) {
    cleaned = cleaned.replace(/^```(?:json)?\n?/i, '');
    cleaned = cleaned.replace(/\n?```$/i, '');
  }
  return cleaned.trim();
}

export function parseVisionResult(responseText) {
  let result = {};
  try {
    result = JSON.parse(cleanJSONString(String(responseText || '')));
  } catch {
    const text = String(responseText || '');
    const idMatch = text.match(/"matchedId"\s*:\s*"([^"]+)"/i);
    const confidenceMatch = text.match(/"confidence"\s*:\s*([0-9.]+)/i);
    result = {
      matchedId: idMatch?.[1] || 'none',
      confidence: confidenceMatch ? Number(confidenceMatch[1]) : 0
    };
  }

  const allowedIds = new Set(sortableTrashItems.map(item => item.id));
  const matchedId = allowedIds.has(result.matchedId) ? result.matchedId : 'none';
  const confidence = Math.max(0, Math.min(1, Number(result.confidence) || 0));
  return { matchedId, confidence, reason: String(result.reason || '') };
}

export function shouldFallbackFromQwenError(status, code = '', message = '') {
  return status === 401
    || status === 403
    || /quota|expired|invalid.*key/i.test(`${code} ${message}`);
}

export async function callQwenVision(base64Images) {
  const images = (Array.isArray(base64Images) ? base64Images : [base64Images]).filter(Boolean);
  if (!images.length) return null;

  try {
    const response = await fetch('/api/qwen-vision', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ images })
    });

    if (!response.ok) {
      const errorText = await response.text();
      let errorData = {};
      try {
        errorData = JSON.parse(errorText);
      } catch {
        errorData = { message: errorText };
      }
      const code = errorData.error?.code || errorData.code || `HTTP_${response.status}`;
      const message = errorData.error?.message || errorData.message || 'Qwen proxy request failed';
      const shouldFallback = shouldFallbackFromQwenError(response.status, code, message);
      console.error(`[AI] Qwen proxy HTTP ${response.status}: ${code}`);
      return {
        matchedId: 'none',
        confidence: 0,
        error: { status: response.status, code, message },
        shouldFallback
      };
    }
    return parseVisionResult(JSON.stringify(await response.json()));
  } catch (error) {
    console.error('[AI] Qwen proxy request failed:', error.message);
    return {
      matchedId: 'none',
      confidence: 0,
      error: { status: 0, code: 'NetworkError', message: error.message },
      shouldFallback: false
    };
  }
}

export async function callGeminiVision(base64Image) {
  const key = localStorage.getItem('gemini_api_key');
  if (!key) {
    console.warn('Chưa cấu hình Gemini API Key.');
    return null;
  }

  const url = `https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=${key}`;
  const dbIds = sortableTrashItems.map(item => item.id).join(', ');

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
      throw new Error('Gemini API returned empty candidates list.');
    }

    const responseText = data.candidates[0].content.parts[0].text;
    console.log('Raw Gemini API Response:', responseText);

    let matchedId = 'none';
    let confidence = 0.0;

    try {
      const cleaned = cleanJSONString(responseText);
      const result = JSON.parse(cleaned);
      matchedId = result.matchedId || 'none';
      confidence = result.confidence || 0.0;
    } catch (parseErr) {
      console.warn('JSON.parse failed. Retrying with regex extraction...', parseErr);
      const idMatch = responseText.match(/"matchedId"\s*:\s*"([^"]+)"/);
      const confMatch = responseText.match(/"confidence"\s*:\s*([0-9.]+)/);

      if (idMatch) matchedId = idMatch[1];
      if (confMatch) confidence = parseFloat(confMatch[1]);
    }

    console.log(`Parsed Gemini result -> id: ${matchedId}, confidence: ${confidence}`);
    return { matchedId, confidence };
  } catch (err) {
    console.error('Gemini Vision API error details:', err);
    return null;
  }
}
