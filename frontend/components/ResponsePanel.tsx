"use client";

import { useState } from "react";
import { type QueryResponse } from "@/lib/types";

interface ResponsePanelProps {
  response: QueryResponse | null;
  loading: boolean;
  error: string | null;
  onRetry: () => void;
}

function ConfidenceBadge({ level }: { level: string }) {
  const colors: Record<string, string> = {
    HIGH: "bg-emerald-500/15 text-emerald-400 ring-emerald-500/30",
    MEDIUM: "bg-amber-500/15 text-amber-400 ring-amber-500/30",
    LOW: "bg-red-500/15 text-red-400 ring-red-500/30",
  };
  const cls = colors[level.toUpperCase()] ?? colors.MEDIUM;

  return (
    <span className={`rounded-full px-2 py-0.5 text-xs font-medium ring-1 ${cls}`}>
      {level}
    </span>
  );
}

function formatAnswer(text: string): React.ReactNode[] {
  const lines = text.split("\n");
  const nodes: React.ReactNode[] = [];

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    if (line.startsWith("```")) {
      const codeLines: string[] = [];
      i++;
      while (i < lines.length && !lines[i].startsWith("```")) {
        codeLines.push(lines[i]);
        i++;
      }
      nodes.push(
        <pre
          key={`code-${i}`}
          className="my-2 overflow-x-auto rounded-lg bg-slate-900 p-3 text-xs text-slate-300"
        >
          <code>{codeLines.join("\n")}</code>
        </pre>
      );
      continue;
    }

    if (line.startsWith("- ") || line.startsWith("* ")) {
      nodes.push(
        <li key={`li-${i}`} className="ml-4 list-disc text-sm text-slate-300">
          {formatInline(line.slice(2))}
        </li>
      );
      continue;
    }

    if (/^\d+\.\s/.test(line)) {
      nodes.push(
        <li key={`ol-${i}`} className="ml-4 list-decimal text-sm text-slate-300">
          {formatInline(line.replace(/^\d+\.\s/, ""))}
        </li>
      );
      continue;
    }

    if (line.trim() === "") {
      nodes.push(<div key={`br-${i}`} className="h-2" />);
      continue;
    }

    nodes.push(
      <p key={`p-${i}`} className="text-sm leading-relaxed text-slate-300">
        {formatInline(line)}
      </p>
    );
  }

  return nodes;
}

function formatInline(text: string): React.ReactNode {
  const parts = text.split(/(`[^`]+`|\*\*[^*]+\*\*)/g);
  return parts.map((part, i) => {
    if (part.startsWith("`") && part.endsWith("`")) {
      return (
        <code
          key={i}
          className="rounded bg-slate-800 px-1 py-0.5 text-xs text-emerald-400"
        >
          {part.slice(1, -1)}
        </code>
      );
    }
    if (part.startsWith("**") && part.endsWith("**")) {
      return (
        <strong key={i} className="font-semibold text-white">
          {part.slice(2, -2)}
        </strong>
      );
    }
    return part;
  });
}

export default function ResponsePanel({
  response,
  loading,
  error,
  onRetry,
}: ResponsePanelProps) {
  const [citationsOpen, setCitationsOpen] = useState(false);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center rounded-xl border border-slate-800 bg-slate-900/50 p-12">
        <svg
          className="mb-4 h-8 w-8 animate-spin text-emerald-400"
          viewBox="0 0 24 24"
          fill="none"
        >
          <circle
            className="opacity-25"
            cx="12"
            cy="12"
            r="10"
            stroke="currentColor"
            strokeWidth="4"
          />
          <path
            className="opacity-75"
            fill="currentColor"
            d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"
          />
        </svg>
        <p className="text-sm font-medium text-slate-300">
          Analyzing codebase…
        </p>
        <p className="mt-1 text-xs text-slate-500">
          First request may take up to 30 seconds while the server warms up.
        </p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-xl border border-red-900/50 bg-red-950/20 p-6">
        <p className="text-sm text-red-400">{error}</p>
        <button
          onClick={onRetry}
          className="mt-3 rounded-lg bg-red-600/20 px-4 py-1.5 text-xs font-medium text-red-300 ring-1 ring-red-500/30 transition-colors hover:bg-red-600/30"
        >
          Try again
        </button>
      </div>
    );
  }

  if (!response) {
    return (
      <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-slate-800 p-12 text-center">
        <div className="mb-3 text-3xl">🔍</div>
        <p className="text-sm text-slate-400">
          Select a feature and ask a question about COBOL or Fortran code
        </p>
      </div>
    );
  }

  const chunks = response.chunks ?? [];

  return (
    <div className="space-y-4 rounded-xl border border-slate-800 bg-slate-900/50 p-5 sm:p-6">
      {/* Answer */}
      <div className="max-h-[60vh] space-y-1 overflow-y-auto pr-1">
        {formatAnswer(response.answer)}
      </div>

      {/* Citations */}
      {chunks.length > 0 && (
        <div className="border-t border-slate-800 pt-4">
          <button
            onClick={() => setCitationsOpen(!citationsOpen)}
            className="flex items-center gap-1.5 text-xs font-medium text-slate-400 hover:text-slate-200"
          >
            <svg
              className={`h-3.5 w-3.5 transition-transform ${citationsOpen ? "rotate-90" : ""}`}
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M9 5l7 7-7 7"
              />
            </svg>
            {chunks.length} source{chunks.length !== 1 ? "s" : ""} cited
          </button>

          {citationsOpen && (
            <div className="mt-3 space-y-2">
              {chunks.map((chunk, idx) => (
                <div
                  key={idx}
                  className="rounded-lg border border-slate-800 bg-slate-900 p-3"
                >
                  <div className="flex items-start justify-between gap-2">
                    <code className="text-xs text-emerald-400">
                      {chunk.file_path}:{chunk.line_start}-{chunk.line_end}
                    </code>
                    <span className="shrink-0 rounded bg-slate-800 px-1.5 py-0.5 text-[10px] text-slate-500">
                      {chunk.name}
                    </span>
                  </div>
                  <pre className="mt-2 max-h-40 overflow-auto text-[11px] leading-relaxed text-slate-500">
                    {chunk.content}
                  </pre>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Metadata bar */}
      <div className="flex flex-wrap items-center gap-3 border-t border-slate-800 pt-3 text-xs text-slate-500">
        {response.confidence && (
          <ConfidenceBadge level={response.confidence} />
        )}
        {response.latency_ms > 0 && (
          <span>{(response.latency_ms / 1000).toFixed(1)}s</span>
        )}
        {response.model && <span>Model: {response.model}</span>}
        {response.codebase_filter && (
          <span>Codebase: {response.codebase_filter}</span>
        )}
      </div>
    </div>
  );
}
