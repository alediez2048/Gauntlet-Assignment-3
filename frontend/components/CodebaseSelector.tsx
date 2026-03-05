"use client";

import { useState, useEffect } from "react";

const LABEL_MAP: Record<string, string> = {
  gnucobol: "GnuCOBOL",
  "opencobol-contrib": "OpenCOBOL Contrib",
  lapack: "LAPACK",
  blas: "BLAS",
  gfortran: "GNU Fortran",
};

interface CodebaseItem {
  name: string;
  language: string;
  description: string;
}

interface CodebaseSelectorProps {
  selected: string | null;
  onSelect: (codebase: string | null) => void;
  disabled?: boolean;
}

export default function CodebaseSelector({
  selected,
  onSelect,
  disabled,
}: CodebaseSelectorProps) {
  const [codebases, setCodebases] = useState<CodebaseItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function fetchCodebases() {
      try {
        const res = await fetch("/api/codebases");
        const data = await res.json();

        if (cancelled) return;

        if (!res.ok) {
          setError(data.error || "Failed to load codebases");
          setCodebases([]);
          return;
        }

        setCodebases(data.codebases ?? []);
        setError(null);
      } catch {
        if (!cancelled) {
          setError("Failed to load codebases");
          setCodebases([]);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    fetchCodebases();
    return () => {
      cancelled = true;
    };
  }, []);

  if (loading) {
    return (
      <div className="flex flex-wrap gap-2">
        <span className="rounded-full px-3 py-1.5 text-xs text-slate-500 sm:text-sm">
          Loading codebases…
        </span>
      </div>
    );
  }

  const options = [
    { value: null, label: "All codebases" },
    ...codebases.map((cb) => ({
      value: cb.name,
      label: LABEL_MAP[cb.name] ?? cb.name,
    })),
  ];

  return (
    <div className="flex flex-wrap gap-2">
      {options.map((opt) => {
        const isActive =
          opt.value === null ? selected === null : selected === opt.value;
        return (
          <button
            key={opt.value ?? "all"}
            onClick={() => onSelect(opt.value)}
            disabled={disabled}
            title={opt.value ? undefined : "Search across all indexed codebases"}
            className={`rounded-full px-3 py-1.5 text-xs font-medium transition-all sm:px-4 sm:text-sm ${
              isActive
                ? "bg-emerald-500/20 text-emerald-300 ring-1 ring-emerald-500/40"
                : "bg-slate-800 text-slate-400 hover:bg-slate-700 hover:text-slate-200"
            } ${disabled ? "cursor-not-allowed opacity-50" : "cursor-pointer"}`}
          >
            {opt.label}
          </button>
        );
      })}
      {error && (
        <span className="text-xs text-amber-500" title={error}>
          (Using All)
        </span>
      )}
    </div>
  );
}
