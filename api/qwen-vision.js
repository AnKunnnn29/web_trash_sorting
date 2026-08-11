import { sortableTrashItems } from '../src/mockData.js';

const QWEN_API_URL = 'https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions';
const QWEN_MODEL = 'qwen3.6-flash';
const MAX_IMAGES = 3;
const MAX_IMAGE_BASE64_LENGTH = 650_000;
const MAX_TOTAL_BASE64_LENGTH = 1_800_000;
const RATE_LIMIT_MAX = 24;
const RATE_LIMIT_WINDOW_MS = 60_000;
const requestBuckets = new Map();

function jsonResult(status, body, headers = {}) {
  return {
    status,
    headers: { 'Content-Type': 'application/json; charset=utf-8', ...headers },
    body
  };
}

function getAllowedOrigins(configuredOrigins = '') {
  return String(configuredOrigins)
    .split(',')
    .map(origin => origin.trim())
    .filter(Boolean);
}

export function isOriginAllowed(origin, host, configuredOrigins = '') {
  if (!origin) return false;
  const explicitOrigins = getAllowedOrigins(configuredOrigins);
  if (explicitOrigins.length) return explicitOrigins.includes(origin);

  try {
    return new URL(origin).host === host;
  } catch {
    return false;
  }
}

function checkRateLimit(ip, now = Date.now()) {
  const key = ip || 'unknown';
  const bucket = requestBuckets.get(key);
  if (!bucket || now - bucket.startedAt >= RATE_LIMIT_WINDOW_MS) {
    requestBuckets.set(key, { startedAt: now, count: 1 });
    return { allowed: true, retryAfter: 0 };
  }

  bucket.count += 1;
  if (bucket.count <= RATE_LIMIT_MAX) return { allowed: true, retryAfter: 0 };
  return {
    allowed: false,
    retryAfter: Math.max(1, Math.ceil((RATE_LIMIT_WINDOW_MS - (now - bucket.startedAt)) / 1000))
  };
}

export function validateImages(images) {
  if (!Array.isArray(images) || images.length < 1 || images.length > MAX_IMAGES) {
    return 'Yêu cầu phải chứa từ 1 đến 3 ảnh.';
  }

  let totalLength = 0;
  for (const image of images) {
    if (typeof image !== 'string' || !image.length) return 'Ảnh không hợp lệ.';
    const base64 = image.startsWith('data:') ? image.split(',')[1] || '' : image;
    if (!/^[A-Za-z0-9+/=]+$/.test(base64)) return 'Ảnh phải sử dụng mã hóa Base64.';
    if (base64.length > MAX_IMAGE_BASE64_LENGTH) return 'Một ảnh vượt quá kích thước cho phép.';
    totalLength += base64.length;
  }

  if (totalLength > MAX_TOTAL_BASE64_LENGTH) return 'Tổng kích thước ảnh vượt quá giới hạn.';
  return null;
}

function cleanJSONString(value) {
  return String(value || '')
    .trim()
    .replace(/^```(?:json)?\s*/i, '')
    .replace(/\s*```$/i, '')
    .trim();
}

function parseModelResult(responseText) {
  let parsed;
  try {
    parsed = JSON.parse(cleanJSONString(responseText));
  } catch {
    return { matchedId: 'none', confidence: 0, reason: '' };
  }

  const allowedIds = new Set(sortableTrashItems.map(item => item.id));
  return {
    matchedId: allowedIds.has(parsed.matchedId) ? parsed.matchedId : 'none',
    confidence: Math.max(0, Math.min(1, Number(parsed.confidence) || 0)),
    reason: String(parsed.reason || '').slice(0, 160)
  };
}

export async function handleQwenVisionRequest({
  method,
  origin,
  host,
  ip,
  body,
  apiKey,
  allowedOrigins = '',
  fetchImpl = fetch
}) {
  if (method !== 'POST') return jsonResult(405, { error: { code: 'MethodNotAllowed' } }, { Allow: 'POST' });
  if (!isOriginAllowed(origin, host, allowedOrigins)) {
    return jsonResult(403, { error: { code: 'OriginNotAllowed' } });
  }

  const rateLimit = checkRateLimit(ip);
  if (!rateLimit.allowed) {
    return jsonResult(
      429,
      { error: { code: 'RateLimitExceeded', message: 'Quá nhiều yêu cầu nhận diện.' } },
      { 'Retry-After': String(rateLimit.retryAfter) }
    );
  }

  if (!apiKey) {
    return jsonResult(503, {
      error: { code: 'ServerMissingApiKey', message: 'QWEN_API_KEY chưa được cấu hình trên server.' }
    });
  }

  const images = body?.images;
  const validationError = validateImages(images);
  if (validationError) {
    return jsonResult(400, { error: { code: 'InvalidImages', message: validationError } });
  }

  const catalog = sortableTrashItems
    .map(item => `${item.id}: ${item.name}${item.keywords?.length ? ` (${item.keywords.join(', ')})` : ''}`)
    .join('; ');
  const content = images.map(image => ({
    type: 'image_url',
    image_url: { url: image.startsWith('data:') ? image : `data:image/jpeg;base64,${image}` }
  }));
  content.push({
    type: 'text',
    text: `Classify the main waste object held near the center of these consecutive camera frames. Ignore hands, people and background. Choose exactly one ID from this catalog: ${catalog}. If there is no clear waste object, use none. Return strict JSON only: {"matchedId":"id_or_none","confidence":0.0,"reason":"short reason"}. Confidence must be between 0 and 1.`
  });

  try {
    const upstream = await fetchImpl(QWEN_API_URL, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${apiKey}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        model: QWEN_MODEL,
        messages: [
          { role: 'system', content: "You are a precise waste-object classifier for a children's sorting station." },
          { role: 'user', content }
        ],
        response_format: { type: 'json_object' },
        enable_thinking: false,
        temperature: 0,
        max_tokens: 200
      })
    });

    if (!upstream.ok) {
      const errorText = await upstream.text();
      let errorData = {};
      try {
        errorData = JSON.parse(errorText);
      } catch {
        errorData = { message: errorText };
      }
      return jsonResult(upstream.status, {
        error: {
          code: errorData.code || errorData.error?.code || `QwenHTTP_${upstream.status}`,
          message: errorData.message || errorData.error?.message || 'Qwen request failed'
        }
      });
    }

    const data = await upstream.json();
    const messageContent = data.choices?.[0]?.message?.content;
    const responseText = Array.isArray(messageContent)
      ? messageContent.map(part => part.text || '').join('')
      : messageContent;
    return jsonResult(200, parseModelResult(responseText));
  } catch (error) {
    console.error('[API] Qwen Vision request failed:', error.message);
    return jsonResult(502, { error: { code: 'QwenNetworkError', message: 'Không kết nối được Qwen.' } });
  }
}

export default async function handler(request, response) {
  const forwardedFor = request.headers['x-forwarded-for'];
  const ip = Array.isArray(forwardedFor)
    ? forwardedFor[0]
    : String(forwardedFor || request.socket?.remoteAddress || 'unknown').split(',')[0].trim();
  const result = await handleQwenVisionRequest({
    method: request.method,
    origin: request.headers.origin,
    host: request.headers.host,
    ip,
    body: request.body,
    apiKey: process.env.QWEN_API_KEY,
    allowedOrigins: process.env.QWEN_ALLOWED_ORIGINS || ''
  });

  Object.entries(result.headers).forEach(([name, value]) => response.setHeader(name, value));
  response.status(result.status).json(result.body);
}
