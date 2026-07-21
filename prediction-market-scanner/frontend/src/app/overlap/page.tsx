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

export default function OverlapPage() {
  const [minProb, setMinProb] = useState(85);

  const { data: overlaps, error, isLoading } = useSWR(
    `/api/whales/overlap/markets?min_prob=${minProb / 100}`,
    fetcher,
    { refreshInterval: 120_000 }
  );

  return (
    <div className="max-w-2xl mx-auto px-4 py-6">
      <div className="mb-6">
        <h1 className="text-xl font-bold text-white">Overlap</h1>
        <p className="text-xs text-slate-400">
          High-probability markets where top whales have open positions — the strongest combined signal
        </p>
      </div>

      {/* Threshold */}
      <div className="bg-slate-800 border border-slate-700 rounded-xl p-4 mb-5">
        <div className="flex justify-between text-sm mb-1">
          <span className="text-slate-300">Min market probability</span>
          <span className="text-green-400 font-bold">{minProb}%</span>
        </div>
        <input
          type="range"
          min={70}
          max={99}
          value={minProb}
          onChange={(e) => setMinProb(Number(e.target.value))}
          className="w-full accent-green-500"
        />
      </div>

      {isLoading && (
        <div className="text-center text-slate-400 py-12">Finding overlaps…</div>
      )}
      {error && (
        <div className="text-center text-red-400 py-12">Could not load overlaps.</div>
      )}
      {overlaps && overlaps.length === 0 && (
        <div className="text-center text-slate-500 py-12">
          No overlaps found at {minProb}%. Try lowering the threshold,
          or run a market scan and whale scan first.
        </div>
      )}

      {overlaps && overlaps.length > 0 && (
        <div className="space-y-4">
          <p className="text-xs text-slate-500">{overlaps.length} overlaps found</p>
          {overlaps.map((item: any, i: number) => (
            <div
              key={i}
              className="bg-slate-800 border border-green-800 rounded-xl p-4"
            >
              {/* Market */}
              <div className="flex items-start gap-2 mb-3">
                <span className="bg-green-500 text-white text-sm font-bold px-2 py-0.5 rounded-full shrink-0">
                  {Math.round(item.probability * 100)}%
                </span>
                <p className="text-sm text-slate-100 leading-snug">{item.question}</p>
              </div>

              <div className="flex gap-2 mb-3 flex-wrap">
                <span className="border border-blue-500 text-blue-400 text-xs px-1.5 py-0.5 rounded capitalize">
                  {item.source}
                </span>
                <a
                  href={item.market_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-xs text-slate-400 hover:text-slate-200 underline"
                >
                  View market ↗
                </a>
              </div>

              {/* Whale signal */}
              <div className="bg-slate-700/60 rounded-lg p-3">
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-xs font-bold text-amber-400">🐋 Whale signal</span>
                  <Link
                    href={`/whales/${item.whale.address}`}
                    className="text-xs text-blue-400 hover:text-blue-300 underline"
                  >
                    #{item.whale.rank_month} {item.whale.username}
                  </Link>
                  <span className="text-xs text-green-400 font-medium ml-auto">
                    +{fmt(item.whale.pnl_month)} / 30d
                  </span>
                </div>
                <div className="flex gap-3 text-xs text-slate-400 flex-wrap">
                  <span className={item.whale.position_outcome === "Yes" ? "text-green-400 font-medium" : "text-red-400 font-medium"}>
                    {item.whale.position_outcome} position
                  </span>
                  <span>Value: {fmt(item.whale.position_value)}</span>
                  <span className={item.whale.position_pnl_pct >= 0 ? "text-green-400" : "text-red-400"}>
                    P&L: {item.whale.position_pnl_pct >= 0 ? "+" : ""}{item.whale.position_pnl_pct.toFixed(1)}%
                  </span>
                </div>
              </div>

              <div className="mt-3 flex gap-2">
                <Link
                  href={`/market/${encodeURIComponent(item.market_id)}`}
                  className="flex-1 text-center text-xs bg-slate-700 hover:bg-slate-600 text-white py-1.5 rounded-lg"
                >
                  Research Report
                </Link>
                <a
                  href={item.whale.whale_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex-1 text-center text-xs border border-slate-600 hover:border-slate-400 text-slate-300 py-1.5 rounded-lg"
                >
                  Whale Profile ↗
                </a>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
