"use client";
import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import useSWR from "swr";
import ReactMarkdown from "react-markdown";

const fetcher = (url: string) => fetch(url).then((r) => r.json());

export default function MarketDetail() {
  const params = useParams();
  const router = useRouter();
  const id = decodeURIComponent(params.id as string);

  const [loadingReport, setLoadingReport] = useState(false);
  const [report, setReport] = useState<any>(null);
  const [reportError, setReportError] = useState("");

  const { data: market, error } = useSWR(`/api/markets/${encodeURIComponent(id)}`, fetcher);

  const generateReport = async () => {
    setLoadingReport(true);
    setReportError("");
    try {
      const res = await fetch(`/api/markets/${encodeURIComponent(id)}/report`);
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Failed to generate report");
      }
      setReport(await res.json());
    } catch (e: any) {
      setReportError(e.message);
    } finally {
      setLoadingReport(false);
    }
  };

  if (error) return (
    <div className="max-w-2xl mx-auto px-4 py-8 text-center text-red-400">
      Market not found.
    </div>
  );

  if (!market) return (
    <div className="max-w-2xl mx-auto px-4 py-8 text-center text-slate-400">
      Loading…
    </div>
  );

  const prob = Math.round(market.probability * 100);
  const probColor = prob >= 95 ? "text-green-400" : prob >= 90 ? "text-green-500" : "text-yellow-400";

  return (
    <div className="max-w-2xl mx-auto px-4 py-6">
      {/* Back */}
      <button
        onClick={() => router.back()}
        className="text-slate-400 hover:text-white text-sm mb-5 flex items-center gap-1"
      >
        ← Back
      </button>

      {/* Market header */}
      <div className="bg-slate-800 border border-slate-700 rounded-xl p-5 mb-5">
        <div className="flex items-start gap-3 mb-4">
          <span className={`text-4xl font-black ${probColor}`}>{prob}%</span>
          <p className="text-slate-100 leading-snug pt-1">{market.question}</p>
        </div>

        <div className="grid grid-cols-2 gap-3 text-sm">
          <Stat label="Platform" value={market.source} capitalize />
          <Stat
            label="24h Volume"
            value={market.volume_24h > 0 ? `$${(market.volume_24h / 1000).toFixed(0)}K` : "—"}
          />
          <Stat
            label="Closes"
            value={market.closes_at ? new Date(market.closes_at).toLocaleDateString() : "—"}
          />
          <Stat
            label="Last updated"
            value={new Date(market.last_seen).toLocaleTimeString()}
          />
        </div>

        <a
          href={market.url}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-4 block text-center text-sm text-blue-400 hover:text-blue-300 border border-blue-800 rounded-lg py-2"
        >
          View on {market.source} ↗
        </a>
      </div>

      {/* Research report */}
      <div className="bg-slate-800 border border-slate-700 rounded-xl p-5">
        <h2 className="text-base font-semibold text-white mb-4">Research Report</h2>

        {!report && !loadingReport && (
          <div className="text-center">
            <p className="text-slate-400 text-sm mb-4">
              Generate an AI-powered research report to help you independently verify this market.
            </p>
            <button
              onClick={generateReport}
              className="bg-green-600 hover:bg-green-500 text-white font-medium px-6 py-2 rounded-lg transition-colors"
            >
              Generate Report
            </button>
          </div>
        )}

        {loadingReport && (
          <div className="text-center py-8">
            <div className="text-slate-400 text-sm animate-pulse">
              Analyzing with Claude…
            </div>
            <p className="text-xs text-slate-500 mt-2">This takes ~10 seconds</p>
          </div>
        )}

        {reportError && (
          <div className="text-red-400 text-sm text-center py-4">
            {reportError}
          </div>
        )}

        {report && (
          <div>
            {report.cached && (
              <p className="text-xs text-slate-500 mb-3">
                Cached · Generated {new Date(report.generated_at).toLocaleString()}
              </p>
            )}
            <div className="prose prose-invert prose-sm max-w-none
              prose-headings:text-slate-100 prose-headings:text-sm prose-headings:font-semibold
              prose-p:text-slate-300 prose-p:leading-relaxed
              prose-li:text-slate-300 prose-strong:text-slate-100
              prose-h2:mt-5 prose-h2:mb-2">
              <ReactMarkdown>{report.content}</ReactMarkdown>
            </div>
            <button
              onClick={generateReport}
              disabled={loadingReport}
              className="mt-5 text-xs text-slate-500 hover:text-slate-300 underline"
            >
              Regenerate report
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

function Stat({
  label,
  value,
  capitalize,
}: {
  label: string;
  value: string;
  capitalize?: boolean;
}) {
  return (
    <div className="bg-slate-700/50 rounded-lg p-3">
      <p className="text-xs text-slate-400 mb-0.5">{label}</p>
      <p className={`text-sm font-medium text-slate-100 ${capitalize ? "capitalize" : ""}`}>
        {value}
      </p>
    </div>
  );
}
