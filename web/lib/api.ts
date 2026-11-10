// Thin client for the local BibAIFilter API.
// Packaged build: same origin (/api). Dev server on :3000 → API on 127.0.0.1:8765.

export function apiBase(): string {
  if (typeof window === "undefined") return "";
  const { port, hostname } = window.location;
  if (port === "3000") return `http://${hostname}:8765`;
  return "";
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function handle<T>(r: Response): Promise<T> {
  if (!r.ok) {
    let msg = r.statusText;
    try {
      const j = await r.json();
      msg = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail ?? j);
    } catch {
      /* keep status text */
    }
    throw new ApiError(r.status, msg);
  }
  return r.json() as Promise<T>;
}

export const api = {
  get: <T,>(path: string) => fetch(apiBase() + path).then((r) => handle<T>(r)),
  post: <T,>(path: string, body?: unknown) =>
    fetch(apiBase() + path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    }).then((r) => handle<T>(r)),
  put: <T,>(path: string, body: unknown) =>
    fetch(apiBase() + path, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }).then((r) => handle<T>(r)),
  del: <T,>(path: string) => fetch(apiBase() + path, { method: "DELETE" }).then((r) => handle<T>(r)),
  upload: <T,>(path: string, file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return fetch(apiBase() + path, { method: "POST", body: fd }).then((r) => handle<T>(r));
  },
  url: (path: string) => apiBase() + path,
};

// ---- types ---------------------------------------------------------------

export type Provider = {
  id: string;
  label: string;
  key_env: string;
  key_url: string;
  key: { configured: boolean; source: string | null; hint: string | null };
};

export type ModelSpec = {
  provider: string;
  id: string;
  label: string;
  tier: string;
  status: string;
  temperature: string;
  reasoning_style: string | null;
  reasoning_levels: string[];
  default_reasoning: string | null;
  recommended_reasoning: string | null;
  default_max_output_tokens: number | null;
  price_in: number | null;
  price_out: number | null;
  note: string;
};

export type Catalog = { date: string; models: ModelSpec[] };

export type Workspace = { path: string; source: string; default: string; exports: string };

export type Preset = { id: string; task: "score" | "eligibility"; label: string; description: string; template: string };

export type Dataset = {
  id: string;
  file: string;
  sha256: string;
  format: string;
  columns: string[];
  n_rows: number;
  mapping: Record<string, string | null>;
  preview?: Record<string, string>[];
};

export type RunState = {
  status?: string;
  total?: number;
  done?: number;
  message?: string | null;
  cost_usd?: number;
  started_at?: string;
  finished_at?: string;
  last?: { rid: number; repetition: number; status: string; score: number | null; decision: string | null };
};

export type RunListItem = {
  run_id: string;
  name: string;
  task: string;
  provider: string;
  model: string;
  created_at: string;
  n_records: number;
  repetitions: number;
  state: RunState;
  counts: Record<string, number> | null;
};

export type Call = Record<string, any>;
