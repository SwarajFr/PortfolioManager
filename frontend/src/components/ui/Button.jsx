import { cn } from "../../utils/classNames";

const VARIANTS = {
  primary:
    "border-transparent bg-[var(--color-accent)] text-black hover:brightness-110",
  secondary:
    "border-[var(--color-border-strong)] bg-transparent text-[var(--color-text)] hover:border-[var(--color-accent)] hover:text-[var(--color-accent)]",
  ghost:
    "border-transparent bg-transparent text-[var(--color-text-muted)] hover:text-[var(--color-text)]",
  danger:
    "border-[var(--color-border-strong)] bg-transparent text-[var(--color-loss)] hover:border-[var(--color-loss)]",
};

/** Token-driven accessible button. */
export default function Button({
  children,
  className = "",
  disabled = false,
  type = "button",
  variant = "secondary",
  ...props
}) {
  return (
    <button
      type={type}
      disabled={disabled}
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-[var(--radius-sm)] border px-3.5 py-2 font-mono text-[0.6875rem] font-medium uppercase tracking-[0.1em] transition duration-[var(--duration-fast)]",
        "disabled:cursor-not-allowed disabled:opacity-45",
        VARIANTS[variant],
        className,
      )}
      {...props}
    >
      {children}
    </button>
  );
}
