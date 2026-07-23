export const AI_CONFIG = Object.freeze({
  inputSize: 224,
  defaultThresholdPercent: 45,
  autoConfirmMs: 700,
  autoCooldownMs: 1500,
  previewIntervalMs: 180,
  predictionWindow: 5,
  minStableVotes: 3,
  minConfidenceMargin: 0.08
});

export function normalizeThresholdPercent(value, fallback = AI_CONFIG.defaultThresholdPercent) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return fallback;
  return Math.min(95, Math.max(30, parsed));
}
