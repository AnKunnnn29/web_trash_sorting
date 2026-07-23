import { describe, expect, it } from 'vitest';
import { createPredictionSmoother } from '../src/predictionSmoothing.js';

const item = (id) => ({ id, name: id });
const prediction = (id, confidence) => ({
  item: item(id),
  confidence,
  displayLabel: `${id} ${confidence}`
});

describe('prediction smoothing', () => {
  it('requires three matching votes before accepting a prediction', () => {
    const smoother = createPredictionSmoother();
    expect(smoother.push(prediction('bottle', 0.7)).stable).toBe(false);
    expect(smoother.push(prediction('bottle', 0.8)).stable).toBe(false);
    const result = smoother.push(prediction('bottle', 0.9));
    expect(result.stable).toBe(true);
    expect(result.item.id).toBe('bottle');
    expect(result.confidence).toBeCloseTo(0.8);
  });

  it('selects the label with more votes in the rolling window', () => {
    const smoother = createPredictionSmoother();
    smoother.push(prediction('bottle', 0.7));
    smoother.push(prediction('soda_can', 0.95));
    smoother.push(prediction('bottle', 0.72));
    smoother.push(prediction('soda_can', 0.9));
    const result = smoother.push(prediction('bottle', 0.74));
    expect(result.item.id).toBe('bottle');
  });

  it('clears stale votes when no object is visible', () => {
    const smoother = createPredictionSmoother();
    smoother.push(prediction('bottle', 0.9));
    smoother.push(prediction('bottle', 0.9));
    smoother.push({ item: null, displayLabel: 'Không thấy vật thể' });
    expect(smoother.push(prediction('bottle', 0.9)).stable).toBe(false);
  });
});
