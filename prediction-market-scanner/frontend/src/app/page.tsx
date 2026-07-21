"use client";
import { useState } from "react";
import useSWR from "swr";
import MarketCard from "@/components/MarketCard";

const fetcher = (url: string) => fetch(url).then((r) => r.json());

const SOURCES = ["all", "polymarket", "kalshi"] as const;
type Source = (typeof SOURCES)[number];

export default function Home() {
  const [threshold, setThreshold] = useState(88);
  const [source, setSource] = useState<Source>("all");
  const [scanning, setScanning] = useState(false);

  const params = new URLSearchParams({
    min_prob: (threshold / 100).toString(),
    limit: "100",
  });
  if (source !== "all") params.set("source", source);

  const { data: markets, error, mutate, isLoading } = useSWR(
    `/api/markets?${params}`,
    fetcher,
    { refreshInterval: 60_000 }
  );

  const triggerScan = async () => {
    setScanning(true);
    await fetch("/api/scan", { method: "POST" });
    setTimeout(() => {
      mutate();
      setScanning(false);
    }, 3000);
  };

  return (
    <div className="max-w-2xl mx-auto px-4 py-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold text-white">Market Scanner</h1>
          <p className="text-xs text-slate-400">Polymarket & Kalshi · High-probability events</p>
        </div>
        <button
          onClick={triggerScan}
          disabled={scanning}
          className="bg-slate-700 hover:bg-slate-600 disabled:opacity-50 text-white text-sm px-3 py-1.5 rounded-lg transition-colors"
        >
          {scanning ? "Scanning…" : "↻ Scan"}
        </button>
      </div>

      {/* Filters */}
      <div className="bg-slate-800 border border-slate-700 rounded-xl p-4 mb-5 space-y-4">
        {/* Threshold slider */}
        <div>
          <div className="flex justify-between text-sm mb-1">
            <span className="text-slate-300">Min probability</span>
            <span className="text-green-400 font-bold">{threshold}%</span>
          </div>
          <input
            type="range"
            min={70}
            max={99}
            value={threshold}
            onChange={(e) => setThreshold(Number(e.target.value))}
            className="w-full accent-green-500"
          />
          <div className="flex justify-between text-xs text-slate-500 mt-1">
            <span>70%</span>
            <span>99%</span>
          </div>
        </div>

        {/* Source filter */}
        <div className="flex gap-2">
          {SOURCES.map((s) => (
            <button
              key={s}
              onClick={() => setSource(s)}
              className={`flex-1 text-sm py-1.5 rounded-lg capitalize transition-colors ${
                source === s
                  ? "bg-slate-600 text-white"
                  : "bg-slate-700 text-slate-400 hover:text-slate-200"
              }`}
            >
              {s}
            </button>
          ))}
        </div>
      </div>

      {/* Market list */}
      {isLoading && (
        <div className="text-center text-slate-400 py-12">Loading markets…</div>
      )}
      {error && (
        <div className="text-center text-red-400 py-12">
          Could not load markets. Is the backend running?
        </div>
      )}
      {markets && markets.length === 0 && (
        <div className="text-center text-slate-400 py-12">
          No markets above {threshold}% found. Try lowering the threshold or trigger a scan.
        </div>
      )}
      {markets && markets.length > 0 && (
        <div className="space-y-3">
          <p className="text-xs text-slate-500">{markets.length} markets found</p>
          {markets.map((m: any) => (
            <MarketCard key={m.id} market={m} />
          ))}
        </div>
      )}
    </div>
  );
}
