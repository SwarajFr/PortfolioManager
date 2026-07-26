import { useEffect, useRef, useState } from "react";
import PageShell from "../../components/layout/PageShell";
import Button from "../../components/ui/Button";
import { cn } from "../../utils/classNames";
import { postChat } from "../../services/agentService";

export default function AgentPage() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [pending, setPending] = useState(false);
  const endRef = useRef(null);

  // DOM side effect only (no setState) — safe under react-hooks/set-state-in-effect.
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, pending]);

  async function handleSend(event) {
    event.preventDefault();
    const text = input.trim();
    if (!text || pending) return;

    const history = [...messages, { role: "user", content: text }];
    setMessages(history);
    setInput("");
    setPending(true);
    try {
      const data = await postChat(history.map((m) => ({ role: m.role, content: m.content })));
      const reply = data.error
        ? { role: "assistant", content: data.message || "The agent hit an error.", error: true }
        : { role: "assistant", content: data.reply || "(no answer)", toolCalls: data.tool_calls || [] };
      setMessages((prev) => [...prev, reply]);
    } catch (err) {
      setMessages((prev) => [...prev, { role: "assistant", content: err.message, error: true }]);
    } finally {
      setPending(false);
    }
  }

  return (
    <PageShell eyebrow="Assistant" title="Agent">
      <div className="flex min-h-[60vh] flex-col gap-4">
        <div className="flex-1 space-y-4 overflow-y-auto pr-1">
          {messages.length === 0 ? (
            <p className="font-mono text-[0.75rem] leading-relaxed text-[var(--color-text-muted)]">
              Ask about your holdings, diversification, a screener strategy, or a live quote. The
              assistant runs locally via Ollama and is read-only — it can look things up but never
              places orders.
            </p>
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

        <form onSubmit={handleSend} className="flex items-end gap-2 border-t border-[var(--color-border)] pt-4">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) handleSend(e);
            }}
            rows={2}
            placeholder="Ask about your portfolio…"
            className="flex-1 resize-none rounded-[var(--radius-sm)] border border-[var(--color-border)] bg-transparent px-3 py-2 text-[0.8125rem] text-[var(--color-text)] outline-none focus:border-[var(--color-accent)]"
          />
          <Button type="submit" variant="primary" disabled={pending || !input.trim()}>
            Send
          </Button>
        </form>
      </div>
    </PageShell>
  );
}
