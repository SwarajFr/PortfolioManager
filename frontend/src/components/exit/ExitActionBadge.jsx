/**
 * ExitActionBadge — colour-coded action label for exit signals.
 */
export default function ExitActionBadge({ action }) {
  const base = "text-xs px-2.5 py-[3px] rounded-md border font-semibold tracking-wide uppercase";

  const styles = {
    EXIT:  "bg-red-500/15 border-red-500/30 text-red-400",
    TRIM:  "bg-orange-500/15 border-orange-500/30 text-orange-400",
    WATCH: "bg-yellow-500/15 border-yellow-500/30 text-yellow-400",
    HOLD:  "bg-green-500/15 border-green-500/30 text-green-400",
  };

  return (
    <span className={`${base} ${styles[action] || styles.HOLD}`}>
      {action}
    </span>
  );
}
