"use client";

import { type FeatureConfig, CODEBASE_EXAMPLES } from "@/lib/features";

interface QueryInputProps {
  query: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  feature: FeatureConfig;
  codebase: string | null;
  loading: boolean;
}

export default function QueryInput({
  query,
  onChange,
  onSubmit,
  feature,
  codebase,
  loading,
}: QueryInputProps) {
  const examples =
    (codebase && CODEBASE_EXAMPLES[codebase]?.[feature.value]) ||
    feature.examples;
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey && !loading && query.trim()) {
      e.preventDefault();
      onSubmit();
    }
  };

  return (
    <div className="space-y-3">
      <div className="flex gap-2">
        <input
          type="text"
          value={query}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={feature.placeholder}
          disabled={loading}
          className="flex-1 rounded-lg border border-slate-700 bg-slate-800/50 px-4 py-2.5 text-sm text-white placeholder-slate-500 outline-none transition-colors focus:border-emerald-500/50 focus:ring-1 focus:ring-emerald-500/30 disabled:opacity-50"
        />
        <button
          onClick={onSubmit}
          disabled={loading || !query.trim()}
          className="rounded-lg bg-emerald-600 px-5 py-2.5 text-sm font-medium text-white transition-colors hover:bg-emerald-500 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {loading ? (
            <span className="flex items-center gap-2">
              <svg
                className="h-4 w-4 animate-spin"
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
              Analyzing…
            </span>
          ) : (
            "Analyze"
          )}
        </button>
      </div>

      <div className="flex flex-wrap gap-2">
        <span className="text-xs text-slate-500">Try:</span>
        {examples.map((example) => (
          <button
            key={example}
            onClick={() => onChange(example)}
            disabled={loading}
            className="rounded-md bg-slate-800/60 px-2.5 py-1 text-xs text-slate-400 transition-colors hover:bg-slate-700 hover:text-slate-200 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {example}
          </button>
        ))}
      </div>
    </div>
  );
}
