"use client";

import { FEATURES, type FeatureConfig } from "@/lib/features";

interface FeatureSelectorProps {
  selected: string;
  onSelect: (feature: FeatureConfig) => void;
  disabled?: boolean;
}

export default function FeatureSelector({
  selected,
  onSelect,
  disabled,
}: FeatureSelectorProps) {
  return (
    <div className="flex flex-wrap gap-2">
      {FEATURES.map((feature) => {
        const isActive = feature.value === selected;
        return (
          <button
            key={feature.value}
            onClick={() => onSelect(feature)}
            disabled={disabled}
            title={feature.description}
            className={`rounded-full px-3 py-1.5 text-xs font-medium transition-all sm:px-4 sm:text-sm ${
              isActive
                ? "bg-emerald-500/20 text-emerald-300 ring-1 ring-emerald-500/40"
                : "bg-slate-800 text-slate-400 hover:bg-slate-700 hover:text-slate-200"
            } ${disabled ? "cursor-not-allowed opacity-50" : "cursor-pointer"}`}
          >
            {feature.label}
          </button>
        );
      })}
    </div>
  );
}
