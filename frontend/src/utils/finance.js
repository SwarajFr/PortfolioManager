/**
 * Value → semantic tone name. The tone strings are the keys of the maps in
 * `constants/theme.js`, so these are the one place a number becomes a colour.
 *
 * Kept out of the components deliberately: P&L colouring has to be identical on
 * the overview, the exit table and the fragility panel, and inlining the
 * comparison in each is how the three drift apart.
 */

/** Gain vs. loss. Zero counts as positive — flat is not a loss. */
export function getSignedTone(value) {
  return Number(value || 0) >= 0 ? "positive" : "negative";
}

/**
 * Risk score → tone. Note the inversion against `getSignedTone`: here a *high*
 * number is bad, because the input is an exit or urgency score where 100 is the
 * worst case. The defaults mirror the exit engine's EXIT/WATCH thresholds.
 */
export function getRiskTone(value, thresholds = { high: 70, medium: 30 }) {
  const score = Number(value || 0);
  if (score >= thresholds.high) return "danger";
  if (score >= thresholds.medium) return "warning";
  return "positive";
}

export function clamp(value, min, max) {
  return Math.min(max, Math.max(min, Number(value || 0)));
}
