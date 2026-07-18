export default function LoadingState({ title = "Loading" }) {
  return (
    <div className="flex min-h-[420px] w-full items-center justify-center p-6">
      <div className="flex w-full max-w-xs flex-col items-center gap-4">
        <div className="relative h-px w-full overflow-hidden bg-[var(--color-border)]">
          <div
            className="absolute inset-y-0 left-0 w-1/4 bg-[var(--color-accent)]"
            style={{ animation: "scan 1.1s var(--ease-out) infinite" }}
          />
        </div>
        <span className="font-mono text-[0.625rem] uppercase tracking-[0.2em] text-[var(--color-text-muted)]">
          {title}
        </span>
      </div>
    </div>
  );
}
