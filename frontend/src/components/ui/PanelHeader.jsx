export default function PanelHeader({ eyebrow, title, description, action }) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-4">
      <div>
        {eyebrow ? (
          <div className="font-data text-[var(--text-xs)] font-medium text-[var(--color-text-muted)]">
            {eyebrow}
          </div>
        ) : null}
        {title ? <h2 className="font-display text-[var(--text-lg)] font-semibold tracking-[-0.01em] text-[var(--color-text)]">{title}</h2> : null}
        {description ? <p className="mt-1 max-w-3xl text-[var(--text-sm)] leading-6 text-[var(--color-text-muted)]">{description}</p> : null}
      </div>
      {action}
    </div>
  );
}
