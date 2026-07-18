export default function LastUpdated({ status }) {
  const ts = status?.last_updated;
  const label = ts ? new Date(ts).toLocaleString() : "never";
  const seeding = status && !status.seed_complete;
  return (
    <div className="flex items-center gap-1.5">
      <span
        className={`h-1.5 w-1.5 rounded-full ${
          status?.refreshing ? "bg-[var(--color-warning)]" : "bg-[var(--color-profit)]"
        }`}
      />
      <span className="font-mono text-[0.5625rem] uppercase tracking-[0.14em] text-[var(--color-text-faint)]">
        {seeding ? "Seeding history…" : `Updated · ${label}`}
      </span>
    </div>
  );
}
