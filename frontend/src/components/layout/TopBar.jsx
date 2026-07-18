import { NAV_ITEMS } from "../../constants/navigation";
import { cn } from "../../utils/classNames";

function emitDashboardEvent(name) {
  window.dispatchEvent(new CustomEvent(name));
}

const railButton =
  "inline-flex h-8 items-center justify-center rounded-[var(--radius-sm)] border border-[var(--color-border)] px-3 font-mono text-[0.625rem] font-medium uppercase tracking-[0.12em] text-[var(--color-text-muted)] transition hover:border-[var(--color-border-strong)] hover:text-[var(--color-text)]";

export default function TopBar({ activeItem, onViewChange }) {
  return (
    <header className="sticky top-0 z-30 border-b border-[var(--color-border)] bg-[var(--color-rail)] px-4 py-3 sm:px-6 lg:h-screen lg:w-[212px] lg:shrink-0 lg:border-b-0 lg:border-r lg:px-4 lg:py-5">
      <div className="flex w-full flex-wrap items-center gap-3 lg:h-full lg:flex-col lg:items-stretch lg:gap-6">
        <button
          aria-label="Return to portfolio overview"
          className="flex items-center gap-2 text-left"
          onClick={() => onViewChange("overview")}
          type="button"
        >
          <span className="h-1.5 w-1.5 rounded-full bg-[var(--color-accent)]" />
          <span className="font-display text-[0.9rem] font-bold tracking-[-0.02em] text-[var(--color-text)]">
            Portfolio<span className="text-[var(--color-text-muted)]"> Optimizer</span>
          </span>
        </button>

        <nav className="order-3 flex w-full gap-1 overflow-x-auto lg:order-none lg:flex-col lg:gap-0.5 lg:overflow-visible">
          {NAV_ITEMS.map((item) => {
            const active = item.id === activeItem.id;
            return (
              <button
                key={item.id}
                className={cn(
                  "group relative min-w-fit border-l-2 px-3 py-2 text-left transition",
                  active
                    ? "border-[var(--color-accent)] bg-[var(--color-surface-soft)]"
                    : "border-transparent hover:bg-[var(--color-surface-soft)]",
                )}
                onClick={() => onViewChange(item.id)}
                type="button"
              >
                <span
                  className={cn(
                    "block font-display text-[var(--text-sm)] font-semibold tracking-[-0.01em]",
                    active ? "text-[var(--color-text)]" : "text-[var(--color-text-muted)] group-hover:text-[var(--color-text)]",
                  )}
                >
                  {item.label}
                </span>
                <span
                  className={cn(
                    "hidden font-mono text-[0.5625rem] uppercase tracking-[0.14em] lg:block",
                    active ? "text-[var(--color-accent)]" : "text-[var(--color-text-faint)]",
                  )}
                >
                  {item.eyebrow}
                </span>
              </button>
            );
          })}
        </nav>

        <div className="ml-auto flex items-center gap-2 lg:mt-auto lg:ml-0 lg:flex-col lg:items-stretch">
          <button className={railButton} onClick={() => emitDashboardEvent("dashboard:refresh")} type="button">
            Refresh
          </button>
          <button className={railButton} onClick={() => emitDashboardEvent("dashboard:configure")} type="button">
            Configure
          </button>
          <div className="hidden items-center gap-1.5 pt-1 lg:flex">
            <span className="h-1.5 w-1.5 rounded-full bg-[var(--color-profit)]" />
            <span className="font-mono text-[0.5625rem] uppercase tracking-[0.14em] text-[var(--color-text-faint)]">
              Kite · Live
            </span>
          </div>
        </div>
      </div>
    </header>
  );
}
