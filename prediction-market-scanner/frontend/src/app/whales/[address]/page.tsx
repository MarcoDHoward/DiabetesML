"use client";
import { useParams, useRouter } from "next/navigation";
import useSWR from "swr";

const fetcher = (url: string) => fetch(url).then((r) => r.json());

function fmt(n: number) {
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(2)}M`;
  if (n >= 1_000) return `$${(n / 1_000).toFixed(1)}K`;
  return `$${n.toFixed(0)}`;
}

function PnlText({ pnl }: { pnl: number }) {
  const color = pnl > 0 ? "text-green-400" : "text-red-400";
  return <span className={color}>{pnl > 0 ? "+" : ""}{fmt(pnl)}</span>;
}

export default function WhalePage() {
  const params = useParams();
  const router = useRouter();
  const address = params.address as string;

  const { data: whale, error, isLoading } = useSWR(
    `/api/whales/${address}`,
    fetcher
  );

  if (isLoading) return (
    <div className="max-w-2xl mx-auto px-4 py-8 text-center text-slate-400">Loading…</div>
  );
  if (error || !whale) return (
    <div className="max-w-2xl mx-auto px-4 py-8 text-center text-red-400">Wallet not found.</div>
  );

  return (
    <div className="max-w-2xl mx-auto px-4 py-6">
      <button
        onClick={() => router.back()}
        className="text-slate-400 hover:text-white text-sm mb-5 flex items-center gap-1"
      >
        ← Back
      </button>

      {/* Wallet header */}
      <div className="bg-slate-800 border border-slate-700 rounded-xl p-5 mb-5">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 rounded-full bg-slate-600 flex items-center justify-center text-lg font-bold text-white shrink-0">
            #{whale.rank_month}
          </div>
          <div>
            <h1 className="text-base font-bold text-white">{whale.username}</h1>
            {whale.x_username && (
              <p className="text-xs text-slate-400">@{whale.x_username}</p>
            )}
          </div>
          <a
            href={whale.polymarket_url}
            target="_blank"
            rel="noopener noreferrer"
            className="ml-auto text-xs text-blue-400 hover:text-blue-300 border border-blue-800 px-2 py-1 rounded-lg"
          >
            Profile ↗
          </a>
        </div>

        <div className="grid grid-cols-3 gap-2 text-center">
          <div className="bg-slate-700/50 rounded-lg p-2">
            <p className="text-xs text-slate-400 mb-0.5">30d P&L</p>
            <PnlText pnl={whale.pnl_month} />
          </div>
          <div className="bg-slate-700/50 rounded-lg p-2">
            <p className="text-xs text-slate-400 mb-0.5">All-time P&L</p>
            <PnlText pnl={whale.pnl_all} />
          </div>
          <div className="bg-slate-700/50 rounded-lg p-2">
            <p className="text-xs text-slate-400 mb-0.5">Volume</p>
            <span className="text-sm font-medium text-slate-100">{fmt(whale.volume)}</span>
          </div>
        </div>
      </div>

      {/* Open positions */}
      <h2 className="text-sm font-semibold text-slate-300 mb-3">
        Open Positions ({whale.positions?.length ?? 0})
      </h2>
      {whale.positions?.length === 0 && (
        <p className="text-slate-500 text-sm mb-5">No open positions found.</p>
      )}
      <div className="space-y-2 mb-6">
        {whale.positions?.map((pos: any, i: number) => (
          <a
            key={i}
            href={pos.url || "#"}
            target="_blank"
            rel="noopener noreferrer"
            className="block bg-slate-800 border border-slate-700 rounded-xl p-3 hover:border-slate-500 transition-colors"
          >
            <div className="flex items-start justify-between gap-2 mb-2">
              <p className="text-sm text-slate-100 leading-snug flex-1">{pos.title}</p>
              <span className={`text-xs font-bold px-2 py-0.5 rounded-full shrink-0 ${
                pos.outcome === "Yes" ? "bg-green-600 text-white" : "bg-red-700 text-white"
              }`}>
                {pos.outcome}
              </span>
            </div>
            <div className="flex gap-3 text-xs text-slate-400 flex-wrap">
              <span>Avg: {(pos.avg_price * 100).toFixed(0)}¢</span>
              <span>Now: {(pos.cur_price * 100).toFixed(0)}¢</span>
              <span>Value: {fmt(pos.current_value)}</span>
              <span className={pos.cash_pnl >= 0 ? "text-green-400" : "text-red-400"}>
                P&L: {pos.cash_pnl >= 0 ? "+" : ""}{fmt(pos.cash_pnl)} ({pos.percent_pnl >= 0 ? "+" : ""}{pos.percent_pnl.toFixed(1)}%)
              </span>
            </div>
          </a>
        ))}
      </div>

      {/* Recent trades */}
      <h2 className="text-sm font-semibold text-slate-300 mb-3">
        Recent Trades ({whale.recent_trades?.length ?? 0})
      </h2>
      <div className="space-y-2">
        {whale.recent_trades?.map((trade: any, i: number) => (
          <a
            key={i}
            href={trade.url || "#"}
            target="_blank"
            rel="noopener noreferrer"
            className="block bg-slate-800 border border-slate-700 rounded-xl p-3 hover:border-slate-500 transition-colors"
          >
            <div className="flex items-start gap-2 mb-1">
              <span className={`text-xs font-bold px-2 py-0.5 rounded shrink-0 ${
                trade.side === "BUY" ? "bg-green-700 text-white" : "bg-red-800 text-white"
              }`}>
                {trade.side}
              </span>
              <p className="text-sm text-slate-100 leading-snug">{trade.title}</p>
            </div>
            <div className="flex gap-3 text-xs text-slate-400 ml-1 flex-wrap">
              <span className={trade.outcome === "Yes" ? "text-green-400" : "text-red-400"}>
                {trade.outcome}
              </span>
              <span>@ {(trade.price * 100).toFixed(0)}¢</span>
              <span>{fmt(trade.usdc_size || trade.size * trade.price)}</span>
              <span>{trade.timestamp ? new Date(trade.timestamp * 1000).toLocaleDateString() : ""}</span>
            </div>
          </a>
        ))}
      </div>
    </div>
  );
}
