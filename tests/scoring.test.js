import { describe, expect, it } from 'vitest';
import { scoreSelection } from '../src/scoring.js';

describe('scoreSelection', () => {
  it('increments correct and total for the right bin', () => {
    expect(scoreSelection(
      { correct: 2, total: 3 },
      { category: 'green' },
      'green'
    )).toEqual({ correct: 3, total: 4, isCorrect: true });
  });

  it('only increments total for a wrong bin', () => {
    expect(scoreSelection(
      { correct: 2, total: 3 },
      { category: 'green' },
      'red'
    )).toEqual({ correct: 2, total: 4, isCorrect: false });
  });
});
