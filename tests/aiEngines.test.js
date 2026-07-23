import { describe, expect, it } from 'vitest';
import {
  applyPixelHeuristics,
  findTrashItemByLabel,
  getTopScores
} from '../src/aiEngines.js';

function solidPixels(r, g, b) {
  const pixels = new Uint8ClampedArray(224 * 224 * 4);
  for (let index = 0; index < pixels.length; index += 4) {
    pixels[index] = r;
    pixels[index + 1] = g;
    pixels[index + 2] = b;
    pixels[index + 3] = 255;
  }
  return pixels;
}

describe('AI engine helpers', () => {
  it('returns the two highest scores and their margin', () => {
    expect(getTopScores([0.1, 0.62, 0.2])).toEqual({
      bestIdx: 1,
      bestProb: 0.62,
      secondProb: 0.2,
      margin: 0.42
    });
  });

  it('maps model labels to the frontend catalog', () => {
    expect(findTrashItemByLabel('bottle')?.id).toBe('bottle');
    expect(findTrashItemByLabel('không tồn tại')).toBeNull();
  });

  it('keeps neutral frames unchanged', () => {
    expect(applyPixelHeuristics(solidPixels(50, 80, 70), 'battery', 0.8)).toEqual({
      label: 'battery',
      confidence: 0.8,
      heuristic: null
    });
  });

  it('detects a strongly red frame as the soda-can heuristic', () => {
    const result = applyPixelHeuristics(solidPixels(190, 40, 35), 'bottle', 0.5);
    expect(result.label).toBe('soda_can');
    expect(result.heuristic).toBe('red_soda_can');
  });
});
