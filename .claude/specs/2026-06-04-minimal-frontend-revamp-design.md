# Minimal Soft-Dark Frontend Revamp

**Date:** 2026-06-04
**Status:** Approved

## Goal

Revamp the frontend into a quiet, minimal flat-dark dashboard. Remove all
ornamental decoration (gradients, glows, grid overlays, conic radars). Keep the
three-tab structure (overview / exit / fragility), all data flow, services,
hooks, and compute logic unchanged.

## Decisions

- **Theme:** Soft dark — flat dark gray surfaces, no gradients/glows, one accent.
- **Navigation:** Slim left sidebar (collapses to a top bar on mobile).
- **Scope:** Restyle + simplify markup (trim ornamental wrappers and verbose copy).
- **Fonts:** Keep IBM Plex Sans (UI) + IBM Plex Mono (numbers/labels), used restrainedly.

## Design tokens (`globals.css`, `theme.js`)

- Backgrounds: flat app bg `#0e1116`, surface `#161b22`, one elevated/hover step.
  No `--shadow-glow`. `--shadow-card` reduced to near-zero or removed; favor borders.
- Borders: subtle `rgba(255,255,255,0.08)`; stronger `rgba(255,255,255,0.14)`.
- Text: `#e6edf3` / muted `#8b949e` / faint `#6e7681`.
- Accent: single blue `#4b8dff`, used sparingly (active nav, links, focus ring).
- Semantic: profit green / loss red for P&L only; warning amber for risk badges.
- Type: smaller scale, fewer weights, less letter-spacing. Drop `--text-display`
  hero size; max heading ~1.25rem.
- Remove utility classes: `premium-grid`, `risk-radar`, `shadow-glow`; flatten `pill`.
  Keep `font-data` / `numeric` (tabular nums).

## Layout shell

- **AppShell:** delete both gradient overlay divs + grid; flat bg, simple flex row.
- **Sidebar (`TopBar.jsx`):** slim ~220px left rail. Plain text product mark
  (no glowing PO badge). 3 nav rows: active = accent left-border + subtle bg;
  inactive = muted. Bottom: Refresh + Configure as quiet ghost buttons. Mobile:
  collapses to a top bar.
- **PageShell:** drop bordered hero panel, "Live risk workspace" pill, grid overlay.
  Plain `h1` + one short muted subtitle, then content. Trim verbose page descriptions.

## Shared UI primitives

- **Card:** flat surface + 1px border, no shadow, no gradient layer. `interactive`
  = border-color shift only.
- **Button:** primary = solid accent (no glow); secondary = bordered; ghost;
  danger = muted red. Remove heavy box-shadows.
- **MetricCard:** muted mono label + tabular mono value. No glow. Tone colors only
  for P&L / risk values.
- **DataTable:** drop "Data Grid" eyebrow + rail-gradient header. Plain header row
  (muted mono caps), thin separators, subtle hover. Keep sort affordance.
- **Badges (StatusBadge, ExitActionBadge, AllocationActionBadge):** flatten to
  tinted bg + colored text, smaller, restrained tracking.
- **LoadingState / EmptyState / LoginPage:** restyle to match; no gradients.

## Feature pages (simplify markup only)

- Keep all hooks, services, data shapes, and the `dashboard:refresh` /
  `dashboard:configure` event wiring exactly as-is.
- Remove decorative wrappers, eyebrows, long descriptions.
- Re-tune `heatmapColors.js` to the muted palette; functionally unchanged.
- `eyebrow` / `description` props stay in component APIs (optional) but verbose
  copy is no longer passed.

## Does NOT change

Routing / `activeView`, lazy loading, all `services/`, all `hooks/`, `utils/`
(formatters/finance), backend compute, `navigation.js` ids, refresh/configure
event contract, settings-drawer behavior.

## Success criteria

- `npm run build` and `npm run lint` pass.
- All three tabs render with the same data as before.
- No gradient/glow/grid/radar remains in the rendered UI.
