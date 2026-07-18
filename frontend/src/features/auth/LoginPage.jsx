import Button from "../../components/ui/Button";
import { redirectToKiteLogin } from "../../services/authService";

export default function LoginPage() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-dashboard px-6 py-10 text-[var(--color-text)]">
      <div className="w-full max-w-sm">
        <div className="flex items-center gap-2">
          <span className="h-1.5 w-1.5 rounded-full bg-[var(--color-accent)]" />
          <span className="font-mono text-[0.625rem] font-medium uppercase tracking-[0.18em] text-[var(--color-text-muted)]">
            Kite · Terminal
          </span>
        </div>

        <h1 className="mt-5 font-display text-[1.75rem] font-bold leading-tight tracking-[-0.02em] text-[var(--color-text)]">
          Portfolio<br />Optimizer
        </h1>

        <div className="mt-6 grid grid-cols-3 gap-px border border-[var(--color-border)] bg-[var(--color-border)] font-mono text-[0.625rem] uppercase tracking-[0.1em]">
          {["Allocation", "Exit Signals", "Fragility"].map((label) => (
            <div key={label} className="bg-[var(--color-surface)] px-2.5 py-2.5">
              <div className="text-[var(--color-text-faint)]">{label}</div>
              <div className="mt-1 text-[var(--color-profit)]">Ready</div>
            </div>
          ))}
        </div>

        <Button className="mt-6 w-full" onClick={redirectToKiteLogin} variant="primary">
          Login with Kite
        </Button>
      </div>
    </main>
  );
}
