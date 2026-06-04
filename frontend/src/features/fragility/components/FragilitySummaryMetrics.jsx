import { LineChart, Line, ResponsiveContainer } from "recharts";
import MetricCard from "../../../components/ui/MetricCard";

function enbTone(enb) {
  if (enb >= 6) return "positive";
  if (enb >= 3) return "warning";
  return "negative";
}

function regimeTone(label) {
  if (label === "LOW") return "positive";
  if (label === "RISING") return "warning";
  return "negative";
}

function corrTone(c) {
  if (c < 0.35) return "positive";
  if (c <= 0.6) return "warning";
  return "negative";
}

export default function FragilitySummaryMetrics({ data }) {
  const {
    enb = 0,
    enb_new = 0,
    regime_label = "LOW",
    stress_loss_pct = 0,
    stress_loss_new_pct = 0,
    mean_corr_long = 0,
    enb_history = [],
  } = data;

  const sparkData = enb_history.map((v, i) => ({ i, v }));
  // Sparkline is red if ENB is lower than 5 steps ago, green otherwise
  const enbFalling =
    enb_history.length >= 6 &&
    enb_history[enb_history.length - 1] < enb_history[enb_history.length - 6];
  const sparkColor = enbFalling ? "var(--loss)" : "var(--profit)";

  return (
    <div className="flex flex-col gap-[var(--space-4)]">
      {/* 4 metric cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-[var(--space-3)]">
        <MetricCard
          label="Effective Bets"
          value={enb.toFixed(1)}
          tone={enbTone(enb)}
        />
        <MetricCard
          label="Regime"
          value={regime_label}
          tone={regimeTone(regime_label)}
        />
        <MetricCard
          label="Stress Loss (99% VaR)"
          value={`${stress_loss_pct.toFixed(1)}%`}
          tone="negative"
        />
        <MetricCard
          label="Avg Correlation"
          value={mean_corr_long.toFixed(3)}
          tone={corrTone(mean_corr_long)}
        />
      </div>

      {/* ENB sparkline — only shown when we have history */}
      {sparkData.length > 1 && (
        <div style={{ width: 200, height: 40 }}>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={sparkData}>
              <Line
                type="monotone"
                dataKey="v"
                stroke={sparkColor}
                strokeWidth={1.5}
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Trim summary line */}
      <p
        className="text-[var(--text-3)]"
        style={{ fontSize: "var(--text-xs)" }}
      >
        After applying trim suggestions: ENB{" "}
        <span className="text-[var(--text-1)]">{enb.toFixed(1)}</span>
        {" → "}
        <span className="text-[var(--profit)]">{enb_new.toFixed(1)}</span>
        {"  ·  Stress loss "}
        <span className="text-[var(--text-1)]">{stress_loss_pct.toFixed(1)}%</span>
        {" → "}
        <span style={{ color: stress_loss_new_pct < stress_loss_pct ? "var(--profit)" : "var(--loss)" }}>
          {stress_loss_new_pct.toFixed(1)}%
        </span>
      </p>
    </div>
  );
}
