export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

export async function api<T>(path: string, body?: unknown): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`/api${path}`, {
      method: body === undefined ? 'GET' : 'POST',
      headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ApiError(0, 'Could not reach the server. Check your connection and try again.');
  }
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    const msg =
      data?.error?.message ??
      (Array.isArray(data?.detail) ? `Please check: ${data.detail.map((d: { loc: string[] }) => d.loc.at(-1)).join(', ')}` : null) ??
      `Request failed (${res.status}).`;
    throw new ApiError(res.status, msg);
  }
  return data as T;
}

export interface Source {
  docId: string;
  title: string;
  url: string;
  version: string;
  location?: string | null;
  quote?: string | null;
}

export interface Scheme {
  id: string;
  name: string;
  short: string;
  ministry: string;
  kind: 'central' | 'state';
  status: 'active' | 'paused' | 'discontinued';
  statusNote?: string | null;
  forWhom: string;
  levels: string;
  benefit: string;
  benefitPerYear: number;
  applyUrl: string;
  window: string;
  rules: { id: string; label: string; source: Source }[];
  checks: { text: string; source: Source }[];
  notes: string[];
  documents: { id: string; title: string; url: string; version: string }[];
}

export type Verdict = 'eligible' | 'maybe' | 'not_eligible';
export interface MatchResult {
  scheme: Scheme;
  verdict: Verdict;
  passed: string[];
  failed: string[];
  unknown: string[];
}
export interface MatchResponse {
  results: MatchResult[];
  closed: { scheme: Scheme }[];
  counts: Record<Verdict, number>;
}

export interface Citation {
  n: number;
  docId: string;
  title: string;
  url: string;
  version: string;
  page: number;
  pageLabel: string;
  section: string;
  schemeIds: string[];
  quote: string | null;
  excerpt: string;
}

export interface AskResponse {
  answer: string;
  found: boolean;
  mode: 'llm' | 'extractive' | 'none';
  model?: string;
  citations: Citation[];
  warning?: string;
  grounding?: { cited: number; verified: number; rejectedQuotes: number };
}

export interface CatalogDoc {
  id: string;
  title: string;
  url: string;
  version: string;
  scheme_ids: string[];
  kind: string;
  note?: string;
  status: 'pending' | 'ok' | 'no_text' | 'failed' | null;
  pages: number | null;
  text_pages: number | null;
  chunks: number | null;
  embedded: number | null;
  ingested_at: string | null;
  error: string | null;
}

export interface Status {
  documents: { ok: number; no_text: number; failed: number; pending: number; chunks: number; embedded: number };
  ingesting: boolean;
  llm: boolean;
  llmProvider: string | null;
  embeddings: boolean;
}
