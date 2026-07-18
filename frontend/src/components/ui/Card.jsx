import { cn } from "../../utils/classNames";

/** Flat surface panel used across the dashboard. */
export default function Card({ children, className = "", interactive = false }) {
  return (
    <section
      className={cn(
        "rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-surface)]",
        interactive && "transition duration-[var(--duration-fast)] hover:border-[var(--color-border-strong)]",
        className,
      )}
    >
      {children}
    </section>
  );
}
