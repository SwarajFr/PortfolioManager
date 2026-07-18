import Card from "./Card";
import { cn } from "../../utils/classNames";

export function TableShell({ children, className = "", action, title }) {
  return (
    <Card className={cn("overflow-hidden", className)}>
      {(title || action) ? (
        <div className="flex items-center justify-between gap-3 border-b border-[var(--color-border)] px-4 py-3">
          {title ? (
            <h2 className="font-mono text-[0.6875rem] font-semibold uppercase tracking-[0.14em] text-[var(--color-text)]">
              {title}
            </h2>
          ) : <span />}
          {action}
        </div>
      ) : null}
      <div className="overflow-x-auto">{children}</div>
    </Card>
  );
}

export function TableHeader({ children, className = "" }) {
  return (
    <div
      className={cn(
        "sticky top-0 z-10 grid min-w-max border-b border-[var(--color-border)] bg-[var(--color-surface)] px-4 py-2.5 font-mono text-[0.625rem] font-medium uppercase tracking-[0.1em] text-[var(--color-text-muted)]",
        className,
      )}
    >
      {children}
    </div>
  );
}

export function TableRow({ children, className = "" }) {
  return (
    <div
      className={cn(
        "grid min-w-max border-b border-[var(--color-border)] px-4 py-2.5 text-[var(--text-sm)] text-[var(--color-text)] transition duration-[var(--duration-fast)] last:border-b-0 hover:bg-[var(--color-surface-hover)]",
        className,
      )}
    >
      {children}
    </div>
  );
}

export function SortHeader({ active, align = "left", children, direction, onClick }) {
  return (
    <button
      className={cn(
        "select-none text-left uppercase tracking-[0.1em] transition hover:text-[var(--color-text)] focus-visible:outline-offset-2",
        align === "right" && "text-right",
        align === "center" && "text-center",
        active && "text-[var(--color-accent)]",
      )}
      onClick={onClick}
      type="button"
    >
      {children}
      {active ? <span className="ml-1 text-[var(--color-accent)]">{direction === "asc" ? "↑" : "↓"}</span> : null}
    </button>
  );
}
