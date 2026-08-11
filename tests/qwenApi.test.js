import { describe, expect, it, vi } from 'vitest';
import {
  handleQwenVisionRequest,
  isOriginAllowed,
  validateImages
} from '../api/qwen-vision.js';

const baseRequest = {
  method: 'POST',
  origin: 'https://ecosort.vercel.app',
  host: 'ecosort.vercel.app',
  ip: '203.0.113.10',
  body: { images: ['YWJj'] },
  apiKey: 'server-side-test-key'
};

describe('Qwen Vision server proxy', () => {
  it('allows only same-origin requests by default', () => {
    expect(isOriginAllowed('https://ecosort.vercel.app', 'ecosort.vercel.app')).toBe(true);
    expect(isOriginAllowed('https://attacker.example', 'ecosort.vercel.app')).toBe(false);
  });

  it('validates the bounded image payload', () => {
    expect(validateImages(['YWJj'])).toBeNull();
    expect(validateImages([])).toMatch(/1 đến 3 ảnh/);
    expect(validateImages(['not base64!'])).toMatch(/Base64/);
  });

  it('keeps the API key server-side and returns a validated classification', async () => {
    const fetchImpl = vi.fn(async (_url, options) => {
      expect(options.headers.Authorization).toBe('Bearer server-side-test-key');
      expect(options.body).not.toContain('server-side-test-key');
      return new Response(JSON.stringify({
        choices: [{ message: { content: '{"matchedId":"bottle","confidence":0.91}' } }]
      }), { status: 200, headers: { 'Content-Type': 'application/json' } });
    });

    const result = await handleQwenVisionRequest({ ...baseRequest, fetchImpl });
    expect(result.status).toBe(200);
    expect(result.body).toMatchObject({ matchedId: 'bottle', confidence: 0.91 });
    expect(fetchImpl).toHaveBeenCalledOnce();
  });

  it('forwards free-quota errors without exposing the key', async () => {
    const fetchImpl = vi.fn(async () => new Response(JSON.stringify({
      code: 'AllocationQuota.FreeTierOnly',
      message: 'Free quota exhausted'
    }), { status: 403, headers: { 'Content-Type': 'application/json' } }));

    const result = await handleQwenVisionRequest({
      ...baseRequest,
      ip: '203.0.113.11',
      fetchImpl
    });
    expect(result.status).toBe(403);
    expect(result.body.error.code).toBe('AllocationQuota.FreeTierOnly');
  });
});
