import Button from "./Button";

export default function Drawer({ children, footer, onClose, title }) {
  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <button
        aria-label="Close panel"
        className="absolute inset-0 bg-black/60"
        onClick={onClose}
        type="button"
      />
      <aside className="relative flex h-full w-full max-w-xl flex-col overflow-hidden border-l border-[var(--color-border-strong)] bg-[var(--color-bg-elevated)]">
        <header className="sticky top-0 z-10 flex items-center justify-between border-b border-[var(--color-border)] bg-[var(--color-bg-elevated)] px-5 py-4">
          <h2 className="font-mono text-[0.75rem] font-semibold uppercase tracking-[0.14em] text-[var(--color-text)]">{title}</h2>
          <Button onClick={onClose} variant="ghost" className="px-3">
            Close
          </Button>
        </header>
        <div className="flex-1 overflow-y-auto p-5">{children}</div>
        {footer ? (
          <footer className="sticky bottom-0 border-t border-[var(--color-border)] bg-[var(--color-bg-elevated)] px-5 py-4">
            {footer}
          </footer>
        ) : null}
      </aside>
    </div>
  );
}
