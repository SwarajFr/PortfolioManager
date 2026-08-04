/**
 * Tone name → Tailwind classes. The two maps share their key set, so a tone
 * resolved once (see `utils/finance.js`) renders consistently as either text or
 * a badge.
 *
 * Classes are written out in full rather than composed, because Tailwind scans
 * source for complete class strings — a template literal like
 * `text-[var(--${tone})]` produces nothing at build time.
 *
 * `negative` and `danger` deliberately share `--loss`: they mean different
 * things (a loss vs. a breached limit) but read as the same red, and keeping
 * them separate lets one change later without touching the other.
 */
export const TONE_STYLES = {
  positive: "text-[var(--profit)]",
  negative: "text-[var(--loss)]",
  warning: "text-[var(--warning)]",
  danger: "text-[var(--loss)]",
  info: "text-[var(--color-info)]",
  neutral: "text-[var(--text-1)]",
};

export const BADGE_STYLES = {
  positive: "border-[rgba(49,208,123,0.35)] bg-[rgba(49,208,123,0.1)] text-[var(--profit)]",
  negative: "border-[rgba(250,82,82,0.35)] bg-[rgba(250,82,82,0.1)] text-[var(--loss)]",
  warning: "border-[rgba(224,165,46,0.38)] bg-[rgba(224,165,46,0.1)] text-[var(--warning)]",
  danger: "border-[rgba(250,82,82,0.42)] bg-[rgba(250,82,82,0.12)] text-[var(--loss)]",
  info: "border-[rgba(56,189,248,0.35)] bg-[rgba(56,189,248,0.1)] text-[var(--color-info)]",
  neutral: "border-[var(--color-border-strong)] bg-[var(--color-surface-soft)] text-[var(--color-text-muted)]",
};
