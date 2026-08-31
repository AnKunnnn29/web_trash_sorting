import { describe, expect, it } from 'vitest';
import { AI_CONFIG, normalizeThresholdPercent } from '../src/aiConfig.js';

describe('AI configuration', () => {
  it('keeps the current recognition baseline', () => {
    expect(AI_CONFIG).toMatchObject({
      inputSize: 224,
      defaultThresholdPercent: 45,
      autoConfirmMs: 200,
      predictionWindow: 5,
      minStableVotes: 3,
      minConfidenceMargin: 0.08
    });
  });

  it('normalizes persisted threshold values safely', () => {
    expect(normalizeThresholdPercent('70')).toBe(70);
    expect(normalizeThresholdPercent('bad')).toBe(45);
    expect(normalizeThresholdPercent(5)).toBe(30);
    expect(normalizeThresholdPercent(120)).toBe(95);
  });
});
