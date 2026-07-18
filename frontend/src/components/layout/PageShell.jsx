/** Page frame: terminal-style header (eyebrow · title · meta), then content. */
export default function PageShell({ children, eyebrow, title, meta }) {
  return (
    <div className="mx-auto flex min-h-0 w-full max-w-[1320px] flex-col gap-5">
      {(title || eyebrow || meta) ? (
        <header className="flex flex-wrap items-end justify-between gap-3 border-b border-[var(--color-border)] pb-4">
          <div>
            {eyebrow ? (
              <div className="font-mono text-[0.625rem] font-medium uppercase tracking-[0.16em] text-[var(--color-accent)]">
                {eyebrow}
              </div>
            ) : null}
            {title ? (
              <h1 className="mt-1 font-display text-[var(--text-2xl)] font-bold tracking-[-0.02em] text-[var(--color-text)]">
                {title}
              </h1>
            ) : null}
          </div>
          {meta ? <div className="pb-1">{meta}</div> : null}
        </header>
      ) : null}
      {children}
    </div>
  );
}
