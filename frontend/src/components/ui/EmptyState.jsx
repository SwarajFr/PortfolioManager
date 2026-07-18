import Button from "./Button";

export default function EmptyState({ title = "No data", description, actionLabel, onAction }) {
  return (
    <div className="flex w-full flex-col items-center rounded-[var(--radius-lg)] border border-dashed border-[var(--color-border-strong)] bg-[var(--color-surface)] px-6 py-12 text-center">
      <h3 className="font-mono text-[0.75rem] font-medium uppercase tracking-[0.16em] text-[var(--color-text)]">
        {title}
      </h3>
      {description ? (
        <p className="mx-auto mt-2 max-w-md text-[var(--text-sm)] leading-6 text-[var(--color-text-muted)]">
          {description}
        </p>
      ) : null}
      {actionLabel && onAction ? (
        <Button className="mt-5" onClick={onAction} variant="secondary">
          {actionLabel}
        </Button>
      ) : null}
    </div>
  );
}
