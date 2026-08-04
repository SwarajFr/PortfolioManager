import { useEffect, useRef, useState } from "react";
import PageShell from "../../components/layout/PageShell";
import Button from "../../components/ui/Button";
import { cn } from "../../utils/classNames";
import { postChat } from "../../services/agentService";
import AdvisorProfileDrawer from "./components/AdvisorProfileDrawer";
import { appendMessage, clearChat, setPending, toHistory, useChat } from "./chatStore";

/**
 * Starters that show the shape of a good question. The last two differ only in
 * their numbers on purpose — the horizon and the target are arguments, so those
 * two produce genuinely different lists.
 */
const QUICK_PROMPTS = [
  "What should I sell or top up?",
  "What can I buy for 10% in 3 months?",
  "What can I buy for 5% in 2 months?",
  "How did your last calls do?",
];

export default function AgentPage() {
  const { messages, pending } = useChat();
  const [input, setInput] = useState("");
  const [showProfile, setShowProfile] = useState(false);
  const endRef = useRef(null);

  // DOM side effect only (no setState) — safe under react-hooks/set-state-in-effect.
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, pending]);

  async function send(text) {
    const trimmed = text.trim();
    if (!trimmed || pending) return;

    const outgoing = { role: "user", content: trimmed };
    appendMessage(outgoing);
    setInput("");
    setPending(true);
    try {
      const data = await postChat(toHistory([...messages, outgoing]));
      appendMessage(
        data.error
          ? { role: "assistant", content: data.message || "The assistant hit an error.", error: true }
          : { role: "assistant", content: data.reply || "(no answer)", toolCalls: data.tool_calls || [] },
      );
    } catch (err) {
      appendMessage({ role: "assistant", content: err.message, error: true });
    } finally {
      setPending(false);
    }
  }

  const handleSubmit = (event) => {
    event.preventDefault();
    send(input);
  };

  return (
    <PageShell
      eyebrow="Assistant"
      title="Agent"
      meta={
        <div className="flex items-center gap-2">
          {messages.length > 0 ? (
            <Button onClick={clearChat} variant="ghost">
              New chat
            </Button>
          ) : null}
          <Button onClick={() => setShowProfile(true)} variant="ghost">
            Profile
          </Button>
        </div>
      }
    >
      <div className="flex min-h-[60vh] flex-col gap-4">
        <div className="flex-1 space-y-4 overflow-y-auto pr-1">
          {messages.length === 0 ? (
            <div className="space-y-4">
              <p className="font-mono text-[0.75rem] leading-relaxed text-[var(--color-text-muted)]">
                Ask what to sell, top up, or buy. The analysis runs in Python — the assistant
                reads the ranked result and explains it, so every number it quotes was computed,
                not guessed. Read-only: it never places orders.
              </p>
              <div className="flex flex-wrap gap-2">
                {QUICK_PROMPTS.map((prompt) => (
                  <button
                    key={prompt}
                    className="rounded-[var(--radius-sm)] border border-[var(--color-border)] px-3 py-1.5 text-left font-mono text-[0.6875rem] text-[var(--color-text-muted)] transition hover:border-[var(--color-accent)] hover:text-[var(--color-text)]"
                    onClick={() => send(prompt)}
                    type="button"
                  >
                    {prompt}
                  </button>
                ))}
              </div>
            </div>
          ) : null}

          {messages.map((m, i) => (
            <div
              key={i}
              className={cn(
                "max-w-[85%] rounded-[var(--radius-sm)] border px-3.5 py-2.5 text-[0.8125rem] leading-relaxed",
                m.role === "user"
                  ? "ml-auto border-[var(--color-accent)] bg-[var(--color-surface-soft)] text-[var(--color-text)]"
                  : m.error
                    ? "border-[var(--color-loss)] text-[var(--color-loss)]"
                    : "border-[var(--color-border)] bg-[var(--color-surface-soft)] text-[var(--color-text)]",
              )}
            >
              <p className="whitespace-pre-wrap">{m.content}</p>
              {m.toolCalls && m.toolCalls.length > 0 ? (
                <div className="mt-2 flex flex-wrap gap-1">
                  {m.toolCalls.map((t, j) => (
                    <span
                      key={j}
                      className="rounded-[var(--radius-sm)] border border-[var(--color-border)] px-1.5 py-0.5 font-mono text-[0.5625rem] uppercase tracking-[0.1em] text-[var(--color-text-muted)]"
                    >
                      {t.name}
                    </span>
                  ))}
                </div>
              ) : null}
            </div>
          ))}

          {pending ? (
            <div className="max-w-[85%] rounded-[var(--radius-sm)] border border-[var(--color-border)] bg-[var(--color-surface-soft)] px-3.5 py-2.5">
              <span className="font-mono text-[0.6875rem] uppercase tracking-[0.12em] text-[var(--color-text-muted)]">
                Thinking…
              </span>
            </div>
          ) : null}

          <div ref={endRef} />
        </div>

        <form onSubmit={handleSubmit} className="flex items-end gap-2 border-t border-[var(--color-border)] pt-4">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) handleSubmit(e);
            }}
            rows={2}
            placeholder="e.g. what can I buy for 6% over the next two months?"
            className="flex-1 resize-none rounded-[var(--radius-sm)] border border-[var(--color-border)] bg-transparent px-3 py-2 text-[0.8125rem] text-[var(--color-text)] outline-none focus:border-[var(--color-accent)]"
          />
          <Button type="submit" variant="primary" disabled={pending || !input.trim()}>
            Send
          </Button>
        </form>
      </div>

      {showProfile ? <AdvisorProfileDrawer onClose={() => setShowProfile(false)} /> : null}
    </PageShell>
  );
}
