"use client";
import Link from "next/link";

interface Market {
  id: string;
  source: string;
  question: string;
  probability: number;
  probability_pct: string;
  volume_24h: number;
  closes_at: string;
  url: string;
  cross_platform?: { source: string; probability: number; url: string };
}

function ProbBadge({ prob }: { prob: number }) {
  const pct = Math.round(prob * 100);
  const color =
    pct >= 95 ? "bg-green-500" : pct >= 90 ? "bg-green-600" : "bg-yellow-500";
  return (
    <span className={`${color} text-white text-sm font-bold px-2 py-0.5 rounded-full`}>
      {pct}%
    </span>
  );
}

function SourceBadge({ source }: { source: string }) {
  const color =
    source === "polymarket"
      ? "border-blue-500 text-blue-400"
      : "border-purple-500 text-purple-400";
  return (
    <span className={`border ${color} text-xs px-1.5 py-0.5 rounded capitalize`}>
      {source === "polymarket" ? "Poly" : "Kalshi"}
    </span>
  );
}

function fmt(n: number) {
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `$${(n / 1_000).toFixed(0)}K`;
  return `$${n.toFixed(0)}`;
}

export default function MarketCard({ market }: { market: Market }) {
  return (
    <Link href={`/market/${encodeURIComponent(market.id)}`}>
      <div className="bg-slate-800 border border-slate-700 rounded-xl p-4 hover:border-slate-500 active:scale-[0.98] transition-all cursor-pointer">
        <div className="flex items-start justify-between gap-3 mb-3">
          <p className="text-sm text-slate-100 leading-snug flex-1">{market.question}</p>
          <ProbBadge prob={market.probability} />
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          <SourceBadge source={market.source} />
          {market.volume_24h > 0 && (
            <span className="text-xs text-slate-400">
              {fmt(market.volume_24h)} / 24h
            </span>
          )}
          {market.cross_platform && (
            <span className="text-xs text-slate-400">
              Also on {market.cross_platform.source}:{" "}
              <span className="text-slate-300">
                {Math.round(market.cross_platform.probability * 100)}%
              </span>
            </span>
          )}
          {market.closes_at && (
            <span className="text-xs text-slate-500 ml-auto">
              {new Date(market.closes_at).toLocaleDateString()}
            </span>
          )}
        </div>
      </div>
    </Link>
  );
}
