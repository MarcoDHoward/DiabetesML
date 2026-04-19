"use client";
import Link from "next/link";
import { useState } from "react";
import useSWR from "swr";

const fetcher = (url: string) => fetch(url).then((r) => r.json());

function fmt(n: number) {
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(2)}M`;
  if (n >= 1_000) return `$${(n / 1_000).toFixed(1)}K`;
  return `$${n.toFixed(0)}`;
}

function PnlBadge({ pnl }: { pnl: number }) {
  const color = pnl > 0 ? "text-green-400" : "text-red-400";
  const sign = pnl > 0 ? "+" : "";
  return <span className={`font-bold ${color}`}>{sign}{fmt(pnl)}</span>;
}

export default function WhalesPage() {
  const [scanning, setScanning] = useState(false);
  const { data: whales, error, isLoading, mutate } = useSWR(
    "/api/whales?limit=30",
    fetcher,
    { refreshInterval: 120_000 }
  );

  const triggerScan = async () => {
    setScanning(true);
    await fetch("/api/whales/scan", { method: "POST" });
    setTimeout(() => { mutate(); setScanning(false); }, 5000);
  };

  return (
    <div className="max-w-2xl mx-auto px-4 py-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold text-white">Whale Tracker</h1>
          <p className="text-xs text-slate-400">Top Polymarket traders by monthly P&L</p>
        </div>
        <button
          onClick={triggerScan}
          disabled={scanning}
          className="bg-slate-700 hover:bg-slate-600 disabled:opacity-50 text-white text-sm px-3 py-1.5 rounded-lg"
        >
          {scanning ? "Scanning…" : "↻ Refresh"}
        </button>
      </div>

      {isLoading && (
        <div className="text-center text-slate-400 py-12">Loading whale data…</div>
      )}
      {error && (
        <div className="text-center text-red-400 py-12">
          Could not load whales. Is the backend running?
        </div>
      )}
      {whales && whales.length === 0 && (
        <div className="text-center text-slate-400 py-12">
          No whale data yet. Tap Refresh to scan the Polymarket leaderboard.
        </div>
      )}

      {whales && whales.length > 0 && (
        <div className="space-y-3">
          {whales.map((w: any) => (
            <Link key={w.address} href={`/whales/${w.address}`}>
              <div className="bg-slate-800 border border-slate-700 rounded-xl p-4 hover:border-slate-500 active:scale-[0.98] transition-all cursor-pointer">
                <div className="flex items-center gap-3 mb-3">
                  <div className="w-8 h-8 rounded-full bg-slate-600 flex items-center justify-center text-sm font-bold text-slate-300 shrink-0">
                    {w.rank_month}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold text-slate-100 truncate">
                      {w.username}
                    </p>
                    {w.x_username && (
                      <p className="text-xs text-slate-500">@{w.x_username}</p>
                    )}
                  </div>
                  <div className="text-right shrink-0">
                    <PnlBadge pnl={w.pnl_month} />
                    <p className="text-xs text-slate-500">30d P&L</p>
                  </div>
                </div>

                <div className="flex gap-4 text-xs text-slate-400">
                  <span>All-time: <PnlBadge pnl={w.pnl_all} /></span>
                  <span>Vol: {fmt(w.volume)}</span>
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
