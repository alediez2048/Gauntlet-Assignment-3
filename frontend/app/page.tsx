"use client";

import { useState, useCallback } from "react";
import Header from "@/components/Header";
import FeatureSelector from "@/components/FeatureSelector";
import QueryInput from "@/components/QueryInput";
import ResponsePanel from "@/components/ResponsePanel";
import { FEATURES, type FeatureConfig } from "@/lib/features";
import { type QueryResponse } from "@/lib/types";

export default function Home() {
  const [feature, setFeature] = useState<FeatureConfig>(FEATURES[0]);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [response, setResponse] = useState<QueryResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = useCallback(async () => {
    const trimmed = query.trim();
    if (!trimmed || loading) return;

    setLoading(true);
    setError(null);
    setResponse(null);

    try {
      const res = await fetch("/api/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query: trimmed,
          feature: feature.value,
        }),
      });

      const data = await res.json();

      if (!res.ok) {
        setError(data.error || `Request failed (${res.status})`);
        return;
      }

      setResponse(data as QueryResponse);
    } catch {
      setError(
        "Unable to connect to the server. Please check your connection and try again."
      );
    } finally {
      setLoading(false);
    }
  }, [query, feature, loading]);

  const handleFeatureSelect = useCallback((f: FeatureConfig) => {
    setFeature(f);
    setResponse(null);
    setError(null);
  }, []);

  return (
    <div className="flex min-h-screen flex-col bg-slate-950 text-white">
      <Header />

      <main className="mx-auto w-full max-w-5xl flex-1 px-4 py-8 sm:px-6">
        <div className="space-y-6">
          {/* Feature selector */}
          <section>
            <h2 className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-500">
              Analysis Feature
            </h2>
            <FeatureSelector
              selected={feature.value}
              onSelect={handleFeatureSelect}
              disabled={loading}
            />
            <p className="mt-2 text-xs text-slate-500">
              {feature.description}
            </p>
          </section>

          {/* Query input */}
          <section>
            <QueryInput
              query={query}
              onChange={setQuery}
              onSubmit={handleSubmit}
              feature={feature}
              loading={loading}
            />
          </section>

          {/* Response area */}
          <section>
            <ResponsePanel
              response={response}
              loading={loading}
              error={error}
              onRetry={handleSubmit}
            />
          </section>
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-800 py-4 text-center text-xs text-slate-600">
        Built with Voyage Code 2 &middot; Qdrant &middot; GPT-4o &middot;
        Next.js
      </footer>
    </div>
  );
}
