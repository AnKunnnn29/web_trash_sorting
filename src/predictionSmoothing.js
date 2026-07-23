import { AI_CONFIG } from './aiConfig.js';

export function createPredictionSmoother({
  windowSize = AI_CONFIG.predictionWindow,
  minStableVotes = AI_CONFIG.minStableVotes
} = {}) {
  let history = [];

  function reset() {
    history = [];
  }

  function push(rawPrediction) {
    if (!rawPrediction?.item) {
      reset();
      return {
        item: null,
        confidence: 0,
        displayLabel: rawPrediction?.displayLabel || 'Không thấy vật thể',
        stable: false
      };
    }

    history.push(rawPrediction);
    if (history.length > windowSize) history.shift();

    const votes = new Map();
    history.forEach((prediction) => {
      const id = prediction.item?.id;
      if (!id) return;
      const vote = votes.get(id) || { count: 0, confidenceSum: 0, latest: prediction };
      vote.count += 1;
      vote.confidenceSum += Number(prediction.confidence) || 0;
      vote.latest = prediction;
      votes.set(id, vote);
    });

    let bestVote = null;
    votes.forEach((vote) => {
      if (
        !bestVote
        || vote.count > bestVote.count
        || (vote.count === bestVote.count && vote.confidenceSum > bestVote.confidenceSum)
      ) {
        bestVote = vote;
      }
    });

    if (!bestVote || bestVote.count < minStableVotes) {
      return {
        item: null,
        confidence: Number(rawPrediction.confidence) || 0,
        displayLabel: rawPrediction.displayLabel || 'Đang kiểm tra...',
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

  return { push, reset };
}
