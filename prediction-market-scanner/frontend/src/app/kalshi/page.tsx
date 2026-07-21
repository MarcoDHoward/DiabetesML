"use client";
import { useState } from "react";
import useSWR from "swr";

const fetcher = (url: string) => fetch(url).then((r) => r.json());

const SIGNAL_COLORS: Record<string, string> = {
  amber: "bg-amber-500/20 text-amber-300 border-amber-600",
  purple: "bg-purple-500/20 text-purple-300 border-purple-600",
  green: "bg-green-500/20 text-green-300 border-green-600",
  red: "bg-red-500/20 text-red-300 border-red-600",
  slate: "bg-slate-500/20 text-slate-300 border-slate-600",
};

function fmt(n: number) {
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(2)}M`;
  if (n >= 1_000) return `$${(n / 1_000).toFixed(1)}K`;
  return `$${n.toFixed(0)}`;
}

function SignalBadge({ meta }: { meta: { label: string; color: string; icon: string } }) {
  return (
    <span className={`inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full border ${SIGNAL_COLORS[meta.color] ?? SIGNAL_COLORS.slate}`}>
      {meta.icon} {meta.label}
    </span>
  );
}

export default function KalshiSignalsPage() {
  const [scanning, setScanning] = useState(false);

  const { data: signals, error, isLoading, mutate } = useSWR(
    "/api/kalshi/signals?limit=50",
    fetcher,
    { refreshInterval: 120_000 }
  );

  const { data: health } = useSWR("/api/health", fetcher, { refreshInterval: 30_000 });
  const kalshiConfigured = health?.kalshi_configured;

  const triggerScan = async () => {
    setScanning(true);
    try {
      await fetch("/api/kalshi/scan", { method: "POST" });
      setTimeout(() => { mutate(); setScanning(false); }, 5000);
    } catch {
      setScanning(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto px-4 py-6">
      <div className="flex items-center justify-between mb-2">
        <div>
          <h1 className="text-xl font-bold text-white">Kalshi Signals</h1>
          <p className="text-xs text-slate-400">Smart money patterns from order flow & volume</p>
        </div>
        {kalshiConfigured && (
          <button
            onClick={triggerScan}
            disabled={scanning}
            className="bg-slate-700 hover:bg-slate-600 disabled:opacity-50 text-white text-sm px-3 py-1.5 rounded-lg"
          >
            {scanning ? "Scanning…" : "↻ Scan"}
          </button>
        )}
      </div>

      {/* Signal legend */}
      <div className="bg-slate-800 border border-slate-700 rounded-xl p-4 mb-5">
        <p className="text-xs font-semibold text-slate-400 mb-2">What each signal means</p>
        <div className="grid grid-cols-2 gap-1.5 text-xs text-slate-400">
          <div>📈 <b className="text-slate-300">Volume Spike</b> — 24h vol 2.5× baseline</div>
          <div>🔺 <b className="text-slate-300">OI Jump</b> — open interest grew 20%+</div>
          <div>⬆️ <b className="text-slate-300">Price Drift ↑</b> — YES moved 5¢+ up</div>
          <div>⬇️ <b className="text-slate-300">Price Drift ↓</b> — YES moved 5¢+ down</div>
          <div>💚 <b className="text-slate-300">Buy Pressure</b> — bids near ask</div>
          <div>🔴 <b className="text-slate-300">Sell Pressure</b> — asks near bid</div>
        </div>
        <p className="text-xs text-slate-500 mt-2">
          More signals on one market = stronger case for informed trading.
          Kalshi is CFTC-regulated — trader identities are private, but footprints aren't.
        </p>
      </div>

      {/* Not configured state */}
      {!kalshiConfigured && (
        <div className="bg-slate-800 border border-amber-700 rounded-xl p-5 text-center">
          <p className="text-amber-400 font-semibold mb-2">Kalshi API key not configured</p>
          <p className="text-slate-400 text-sm mb-3">
            Add your Kalshi credentials to <code className="text-slate-300 bg-slate-700 px-1 rounded">backend/.env</code> to enable smart money signals.
          </p>
          <div className="text-left bg-slate-900 rounded-lg p-3 text-xs text-slate-300 font-mono">
            <div>KALSHI_API_KEY_ID=your-key-id</div>
            <div>KALSHI_PRIVATE_KEY_PATH=./kalshi_private_key.pem</div>
          </div>
          <a
            href="https://kalshi.com/profile/api"
            target="_blank"
            rel="noopener noreferrer"
            className="mt-3 inline-block text-sm text-blue-400 hover:text-blue-300 underline"
          >
            Get Kalshi API key ↗
          </a>
        </div>
      )}

      {/* Loading / error */}
      {kalshiConfigured && isLoading && (
        <div className="text-center text-slate-400 py-12">Loading signals…</div>
      )}
      {kalshiConfigured && error && (
        <div className="text-center text-red-400 py-12">Could not load signals.</div>
      )}
      {kalshiConfigured && signals?.length === 0 && (
        <div className="text-center text-slate-500 py-12">
          No signals detected yet. Signals appear after 2 scan cycles (signals require a before/after comparison).
          <br /><br />
          <button onClick={triggerScan} className="text-blue-400 underline text-sm">Trigger scan now</button>
        </div>
      )}

      {/* Signal cards */}
      {kalshiConfigured && signals && signals.length > 0 && (
        <div className="space-y-3">
          <p className="text-xs text-slate-500">{signals.length} signals detected</p>
          {signals.map((s: any, i: number) => (
            <a
              key={i}
              href={s.url}
              target="_blank"
              rel="noopener noreferrer"
              className={`block bg-slate-800 border rounded-xl p-4 hover:border-slate-500 transition-colors ${
                s.signals.length >= 3 ? "border-amber-700" : "border-slate-700"
              }`}
            >
              {s.signals.length >= 3 && (
                <div className="text-xs text-amber-400 font-semibold mb-2">
                  ⚡ Multiple signals — strong case
                </div>
              )}

              <p className="text-sm text-slate-100 leading-snug mb-3">{s.title}</p>

              {/* Signal badges */}
              <div className="flex flex-wrap gap-1.5 mb-3">
                {s.signal_meta.map((meta: any, j: number) => (
                  <SignalBadge key={j} meta={meta} />
                ))}
              </div>

              {/* Stats */}
              <div className="flex gap-3 text-xs text-slate-400 flex-wrap">
                <span>YES: <span className="text-slate-200">{s.mid_pct}</span></span>
                {s.volume_24h > 0 && <span>Vol: {fmt(s.volume_24h)}</span>}
                {s.open_interest > 0 && <span>OI: {fmt(s.open_interest)}</span>}
                {s.details.volume_multiplier && (
                  <span className="text-amber-400">{s.details.volume_multiplier}× vol</span>
                )}
                {s.details.oi_change_pct && (
                  <span className="text-purple-400">OI +{s.details.oi_change_pct}%</span>
                )}
                {s.details.price_drift && (
                  <span className={s.details.price_drift > 0 ? "text-green-400" : "text-red-400"}>
                    {s.details.price_drift > 0 ? "+" : ""}{(s.details.price_drift * 100).toFixed(1)}¢ drift
                  </span>
                )}
                {s.close_time && (
                  <span className="ml-auto text-slate-500">
                    {new Date(s.close_time).toLocaleDateString()}
                  </span>
                )}
              </div>
            </a>
          ))}
        </div>
      )}
    </div>
  );
}
