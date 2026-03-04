export interface RetrievedChunk {
  content: string;
  file_path: string;
  line_start: number;
  line_end: number;
  name: string;
  language: string;
  codebase: string;
  score: number;
  confidence: string;
  metadata: Record<string, string>;
}

export interface QueryResponse {
  answer: string;
  chunks: RetrievedChunk[];
  query: string;
  feature: string;
  confidence: string;
  codebase_filter: string | null;
  latency_ms: number;
  model: string;
}

export interface QueryRequest {
  query: string;
  feature: string;
  codebase?: string;
}
