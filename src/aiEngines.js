import { trashItems } from './mockData.js';

const LOCAL_MODEL_URL = '/tfjs_model/model.json';

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

  return trashItems.find(item => item.id === normalized)
    || trashItems.find(item => item.name.toLowerCase() === normalized)
    || trashItems.find(item =>
      item.keywords && item.keywords.some(kw => normalized.includes(kw.toLowerCase()))
    )
    || null;
}

export async function loadConfiguredAIEngine() {
  const savedModelUrl = localStorage.getItem('ai_model_url') || '';
  const geminiKey = localStorage.getItem('gemini_api_key') || '';
  const pythonApiUrl = localStorage.getItem('python_api_url') || 'http://localhost:5000';
  const isLocalHost = location.hostname === 'localhost' || location.hostname === '127.0.0.1';

  if (isLocalHost) {
    try {
      const healthRes = await fetch(`${pythonApiUrl}/health`, {
        method: 'GET',
        signal: AbortSignal.timeout(2000)
      });
      if (healthRes.ok) {
        const healthData = await healthRes.json();
        if (healthData.status === 'ok') {
          console.log('[AI] Python API server available:', pythonApiUrl);
          return {
            model: { _isPythonAPI: true, _apiUrl: pythonApiUrl },
            isCustomModel: true,
            isGeminiActive: false,
            thresholdPercent: 45,
            status: {
              tone: 'success',
              text: '🐍 Python AI API sẵn sàng'
            }
          };
        }
      }
    } catch (err) {
      console.log('[AI] Python API not available:', err.message);
    }
  }

  try {
    console.log('[AI] Checking Local TFJS Graph Model...');
    const localModel = await tf.loadGraphModel(LOCAL_MODEL_URL);
    const labelsRes = await fetch('/tfjs_model/labels.json');
    localModel._localLabels = await labelsRes.json();
    localModel._isGraphModel = true;
    return {
      model: localModel,
      isCustomModel: true,
      isGeminiActive: false,
      thresholdPercent: 45,
      status: {
        tone: 'success',
        text: '⚡ AI cục bộ sẵn sàng'
      }
    };
  } catch (localErr) {
    console.log('[AI] Local TFJS not found or failed:', localErr.message);
  }

  if (savedModelUrl && !savedModelUrl.endsWith('.json')) {
    console.log('[AI] Loading Teachable Machine model:', savedModelUrl);
    if (typeof tmImage === 'undefined') throw new Error('Thiếu thư viện Teachable Machine');

    const base = savedModelUrl.endsWith('/') ? savedModelUrl : `${savedModelUrl}/`;
    return {
      model: await tmImage.load(`${base}model.json`, `${base}metadata.json`),
      isCustomModel: true,
      isGeminiActive: false,
      thresholdPercent: 75,
      status: {
        tone: 'success',
        text: '🎓 Teachable Machine sẵn sàng'
      }
    };
  }

  if (geminiKey) {
    console.log('[AI] Using Gemini Vision API');
    return {
      model: null,
      isCustomModel: false,
      isGeminiActive: true,
      thresholdPercent: 75,
      status: {
        tone: 'accent',
        text: '✨ Gemini Vision sẵn sàng'
      }
    };
  }

  console.log('[AI] Loading MobileNet fallback');
  if (typeof mobilenet === 'undefined') throw new Error('Thiếu thư viện MobileNet');

  return {
    model: await mobilenet.load(),
    isCustomModel: false,
    isGeminiActive: false,
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

export async function callGeminiVision(base64Image) {
  const key = localStorage.getItem('gemini_api_key');
  if (!key) {
    console.warn('Chưa cấu hình Gemini API Key.');
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
