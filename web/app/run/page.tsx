"use client";

import clsx from "clsx";
import { Download, FolderOpen, PauseCircle, PlayCircle } from "lucide-react";
import { FolderPicker } from "@/components/FolderPicker";
import { Fragment, useEffect, useMemo, useState } from "react";
import { PageTitle } from "@/components/AppShell";
import { Badge, Button, Card, ErrorBox, Note, Stat, StatusBadge, fmt } from "@/components/ui";
import { api, Call, RunState } from "@/lib/api";

function useRunId() {
  const [id, setId] = useState<string | null>(null);
  useEffect(() => setId(new URLSearchParams(window.location.search).get("id")), []);
  return id;
}

function RecallCurve({ model, bm25 }: { model?: number[]; bm25?: number[] }) {
  if (!model?.length) return null;
  const W = 420, H = 220, P = 32;
  const path = (c: number[]) => c.map((y, i) => `${i ? "L" : "M"}${P + ((i + 1) / c.length) * (W - 2 * P)},${H - P - y * (H - 2 * P)}`).join(" ");
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full max-w-[460px]">
      <rect x={P} y={P} width={W - 2 * P} height={H - 2 * P} fill="#f7f9fc" stroke="#d8dee8" />
      <line x1={P} y1={H - P - 0.95 * (H - 2 * P)} x2={W - P} y2={H - P - 0.95 * (H - 2 * P)} stroke="#a16207" strokeDasharray="4 3" />
      <path d={`M${P},${H - P} L${W - P},${P}`} stroke="#c9d6e5" strokeDasharray="3 3" />
      {bm25 && <path d={path(bm25)} fill="none" stroke="#7593b5" strokeWidth={2} />}
      <path d={path(model)} fill="none" stroke="#2b6bbb" strokeWidth={2.5} />
      <text x={P} y={H - 8} fontSize="11" fill="#5f6f85">0%</text>
      <text x={W - P - 70} y={H - 8} fontSize="11" fill="#5f6f85">records screened 100%</text>
      <text x={4} y={P + 4} fontSize="11" fill="#5f6f85">recall</text>
      <text x={W - P - 30} y={H - P - 0.95 * (H - 2 * P) - 4} fontSize="10" fill="#a16207">95%</text>
      <g fontSize="11"><rect x={P + 8} y={P + 8} width={10} height={3} fill="#2b6bbb" /><text x={P + 22} y={P + 13}>model</text>
        <rect x={P + 70} y={P + 8} width={10} height={3} fill="#7593b5" /><text x={P + 84} y={P + 13}>BM25</text></g>
    </svg>
  );
}

function MetricRow({ label, a, b, digits = 3 }: { label: string; a: any; b?: any; digits?: number }) {
  return <tr><td className="font-semibold">{label}</td><td>{fmt(a, digits)}</td>{b !== undefined && <td className="text-muted">{fmt(b, digits)}</td>}</tr>;
}

export default function RunPage() {
  const id = useRunId();
  const [detail, setDetail] = useState<any>(null);
  const [state, setState] = useState<RunState>({});
  const [analysis, setAnalysis] = useState<any>(null);
  const [records, setRecords] = useState<any[]>([]);
  const [calls, setCalls] = useState<{ total: number; rows: Call[] }>({ total: 0, rows: [] });
  const [statusFilter, setStatusFilter] = useState("");
  const [open, setOpen] = useState<string | null>(null);
  const [err, setErr] = useState<unknown>(null);
  const [picking, setPicking] = useState(false);
  const [exported, setExported] = useState<string | null>(null);
  const exportTo = (folder: string) => api.post<{ folder: string; files: string[] }>(`/api/runs/${id}/export`, { output_dir: folder })
    .then((r) => { setExported(`${r.files.length} files written to ${r.folder}`); setPicking(false); loadAll(); }).catch(setErr);

  const loadAll = () => {
    if (!id) return;
    api.get<any>(`/api/runs/${id}`).then((d) => { setDetail(d); setState(d.state); }).catch(setErr);
    api.get<any>(`/api/runs/${id}/analysis`).then(setAnalysis).catch(() => undefined);
    api.get<any[]>(`/api/runs/${id}/records`).then(setRecords).catch(() => undefined);
  };
  useEffect(loadAll, [id]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!id) return;
    api.get<{ total: number; rows: Call[] }>(`/api/runs/${id}/calls?limit=500${statusFilter ? `&status=${statusFilter}` : ""}`)
      .then(setCalls).catch(() => undefined);
  }, [id, statusFilter, state.done]);

  useEffect(() => {
    if (!id) return;
    const es = new EventSource(api.url(`/api/runs/${id}/events`));
    let finished = false;
    es.onmessage = (ev) => {
      const st = JSON.parse(ev.data) as RunState;
      setState(st);
      if (["completed", "cancelled", "stopped", "failed"].includes(st.status || "") && !finished) {
        finished = true;
        loadAll();
      }
    };
    es.onerror = () => es.close();
    return () => es.close();
  }, [id, detail?.active]); // eslint-disable-line react-hooks/exhaustive-deps

  const m = detail?.manifest;
  const cfg = m?.config;
  const active = state.status === "running" || state.status === "created";
  const pct = state.total ? Math.round(((state.done || 0) / state.total) * 100) : 0;
  const o = analysis?.outcomes;
  const firstCall = calls.rows[0];
  const sortedRecords = useMemo(() => [...records].sort((a, b) =>
    (b.mean_score ?? b.include ?? -1) - (a.mean_score ?? a.include ?? -1)), [records]);

  if (!id) return null;
  return (
    <>
      <PageTitle
        title={cfg?.name || id}
        subtitle={cfg && <>{cfg.task === "score" ? "Relevance score 1–7" : "Eligibility screening"} · <b>{cfg.provider}/{cfg.model}</b> · {m.n_records} records × {cfg.repetitions} repetitions · run id <span className="font-mono">{id}</span></>}
        actions={<>
          {active && <Button variant="outline" size="sm" onClick={() => api.post(`/api/runs/${id}/cancel`).catch(setErr)}><PauseCircle className="h-4 w-4" />Stop</Button>}
          {!active && state.status && state.status !== "completed" && <Button variant="outline" size="sm" onClick={() => api.post(`/api/runs/${id}/resume`).then(() => { setDetail({ ...detail, active: true }); setState({ ...state, status: "running" }); }).catch(setErr)}><PlayCircle className="h-4 w-4" />Resume</Button>}
          <a href={api.url(`/api/runs/${id}/download/xlsx`)}><Button size="sm"><Download className="h-4 w-4" />Excel</Button></a>
          <a href={api.url(`/api/runs/${id}/download/jsonl`)}><Button variant="outline" size="sm">Call log (JSONL)</Button></a>
          <a href={api.url(`/api/runs/${id}/download/manifest`)}><Button variant="outline" size="sm">Manifest</Button></a>
        </>}
      />
      <ErrorBox error={err} />
      <Card className="mb-5">
        <div className="flex items-center gap-4">
          <StatusBadge status={state.status} />
          <div className="h-2.5 flex-1 overflow-hidden rounded-full bg-bg-soft">
            <div className={clsx("h-full rounded-full transition-all", state.status === "completed" ? "bg-success" : "bg-accent-500")} style={{ width: `${pct}%` }} />
          </div>
          <span className="text-[13px] font-semibold">{state.done ?? 0} / {state.total ?? 0} calls</span>
          {state.cost_usd !== undefined && <span className="text-[13px] text-muted">≈ ${fmt(state.cost_usd, 4)}</span>}
        </div>
        {state.message && <p className="mt-2 text-[13px] text-warning">{state.message}</p>}
        {m && (
          <div className="mt-3 flex flex-wrap items-center gap-3 border-t border-border pt-3 text-[13px]">
            <span className="text-muted">Results folder:</span>
            <span className="font-mono text-[12px]">{m.export_dir || m.output_dir || "—"}</span>
            {!active && <Button size="sm" variant="outline" onClick={() => setPicking(true)}><FolderOpen className="h-4 w-4" />Save a copy to…</Button>}
            {exported && <span className="text-success">{exported}</span>}
          </div>
        )}
      </Card>
      <FolderPicker open={picking} start={m?.export_dir || m?.output_dir} title="Save the results in…" onPick={exportTo} onClose={() => setPicking(false)} />

      {o && (
        <div className="mb-5 grid gap-3 sm:grid-cols-3 lg:grid-cols-6">
          <Stat label="Valid answers" value={o.valid_share == null ? "—" : `${Math.round(o.valid_share * 100)}%`} sub={Object.entries(o.by_status).map(([k, v]) => `${k} ${v}`).join(" · ")} />
          <Stat label="Served model" value={<span className="text-[14px]">{Object.keys(o.served_models)[0] || "—"}</span>} sub={o.model_mismatch_calls ? `${o.model_mismatch_calls} calls differ from requested` : "matches requested"} />
          <Stat label="Retried calls" value={o.retried_calls} />
          <Stat label="Tokens" value={fmt(o.tokens.input + o.tokens.output, 0)} sub={`reasoning ${o.tokens.reasoning}`} />
          <Stat label="Cost" value={o.cost_usd == null ? "unknown" : `$${fmt(o.cost_usd, 4)}`} sub="list prices" />
          <Stat label="Latency" value={o.latency_median_s == null ? "—" : `${fmt(o.latency_median_s, 2)} s`} sub={`median · p90 ${fmt(o.latency_p90_s, 2)} s`} />
        </div>
      )}

      {!analysis && state.status && <div className="mb-5"><Note>Computing the analysis (exact permutation tests and bootstrap intervals)…</Note></div>}
      <div className="grid gap-5 lg:grid-cols-2">
        {analysis?.stability && (
          <Card title="Stability across repetitions" subtitle="How much the answer for the same record changed between repeated calls.">
            <table className="data"><tbody>
              <MetricRow label="Records with any variation" a={analysis.stability.n_records_with_variation} />
              <MetricRow label="Mean between-repetition SD" a={analysis.stability.mean_between_repetition_sd} />
              <MetricRow label="Largest between-repetition SD" a={analysis.stability.max_between_repetition_sd} />
              <MetricRow label="Valid calls" a={`${analysis.stability.n_valid} / ${analysis.stability.n_calls}`} />
            </tbody></table>
          </Card>
        )}
        {firstCall?.params_sent && (
          <Card title="Parameters actually sent" subtitle="As logged for the first call (every call has its own record in the log).">
            <table className="data"><tbody>
              {Object.entries(firstCall.params_sent).map(([k, v]) => <tr key={k}><td className="font-semibold">{k}</td><td>{typeof v === "object" ? JSON.stringify(v) : String(v)}</td></tr>)}
            </tbody></table>
          </Card>
        )}
        {analysis?.reference_agreement && (
          <Card title="Agreement with the reference scores" subtitle="Record means vs. the reference column; BM25 on the same records as a non-LLM baseline.">
            <table className="data">
              <thead><tr><th></th><th>Model</th><th>BM25</th></tr></thead>
              <tbody>
                {(["spearman_rho", "spearman_p_exact", "kendall_tau_b", "mae", "mean_bias", "ccc", "icc_a1"] as const).map((k) => (
                  <MetricRow key={k} label={k.replaceAll("_", " ")} a={analysis.reference_agreement.model[k]} b={analysis.reference_agreement.bm25_baseline[k]} />
                ))}
                <MetricRow label="Spearman 95% CI (bootstrap)" a={analysis.reference_agreement.model.spearman_ci95_percentile?.map((x: number) => x.toFixed(2)).join(" to ")}
                  b={analysis.reference_agreement.bm25_baseline.spearman_ci95_percentile?.map((x: number) => x.toFixed(2)).join(" to ")} />
              </tbody>
            </table>
            <p className="mt-2 text-[12px] text-muted">MAE, bias, CCC and ICC are not meaningful for BM25, which is not on the 1–7 scale.</p>
          </Card>
        )}
        {analysis?.screening && (
          <Card title="Screening performance against the labels" subtitle={`${analysis.screening.n_labelled} labelled records, ${analysis.screening.n_relevant} included.`}>
            <div className="grid gap-4 md:grid-cols-2">
              <table className="data">
                <thead><tr><th></th><th>Model</th><th>BM25</th></tr></thead>
                <tbody>
                  <MetricRow label="Recall (decision)" a={analysis.screening.model_decision.recall} />
                  <MetricRow label="Precision (decision)" a={analysis.screening.model_decision.precision} />
                  <MetricRow label="Specificity" a={analysis.screening.model_decision.specificity} />
                  <MetricRow label="ROC AUC (ranking)" a={analysis.screening.model_ranking.roc_auc} b={analysis.screening.bm25_ranking.roc_auc} />
                  <MetricRow label="WSS@95" a={analysis.screening.model_ranking.wss_95} b={analysis.screening.bm25_ranking.wss_95} />
                  <MetricRow label="Recall @ 25% screened" a={analysis.screening.model_ranking.recall_at_25pct} b={analysis.screening.bm25_ranking.recall_at_25pct} />
                  <MetricRow label="Recall @ 50% screened" a={analysis.screening.model_ranking.recall_at_50pct} b={analysis.screening.bm25_ranking.recall_at_50pct} />
                </tbody>
              </table>
              <RecallCurve model={analysis.screening.model_ranking.recall_curve} bm25={analysis.screening.bm25_ranking.recall_curve} />
            </div>
            <p className="mt-2 text-[12px] text-muted">Decision: {cfg?.task === "score" ? `mean score ≥ ${cfg?.threshold}` : "kept unless every valid repetition said exclude"}. Ranking: records in descending model score (ties broken by BM25); WSS@95 = share of records not screened when 95% of included records are found, minus 5%.</p>
          </Card>
        )}
      </div>

      <Card className="mt-5" title="Records" subtitle="Sorted by model score. Failed calls are counted, never filled in.">
        <div className="-mx-5 -my-4 max-h-[480px] overflow-auto">
          <table className="data">
            <thead><tr><th>#</th><th>Title</th>{cfg?.task === "score" ? <><th>Mean</th><th>SD</th></> : <><th>Incl.</th><th>Unc.</th><th>Excl.</th></>}<th>Valid</th><th>Statuses</th><th>BM25</th><th>Label</th></tr></thead>
            <tbody>
              {sortedRecords.map((r) => (
                <tr key={r.rid}>
                  <td className="text-muted">{r.rid}</td>
                  <td className="max-w-[520px]">{r.title}</td>
                  {cfg?.task === "score" ? <><td className="font-bold">{fmt(r.mean_score, 2)}</td><td>{fmt(r.sd_score, 2)}</td></>
                    : <><td>{r.include}</td><td>{r.uncertain}</td><td>{r.exclude}</td></>}
                  <td>{r.n_valid}/{r.n_calls}</td>
                  <td className="text-[12px] text-muted">{r.statuses}</td>
                  <td>{fmt(r.bm25, 2)}</td>
                  <td>{r.label == null ? "—" : r.label ? <Badge tone="success">include</Badge> : <Badge>exclude</Badge>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <Card className="mt-5" title="Call log" subtitle={`${calls.total} calls${statusFilter ? ` with status “${statusFilter}”` : ""}. Click a row for the raw answer and every HTTP attempt.`}
        actions={<select className="rounded-md border border-border px-2 py-1 text-[13px]" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
          <option value="">all statuses</option>
          {["ok", "extracted", "truncated", "empty", "unparsable", "ambiguous", "out_of_range", "refused", "error", "skipped"].map((s) => <option key={s}>{s}</option>)}
        </select>}>
        <div className="-mx-5 -my-4 max-h-[520px] overflow-auto">
          <table className="data">
            <thead><tr><th>Call</th><th>Status</th><th>Answer</th><th>Served model</th><th>Finish</th><th>Tokens in/out (reasoning)</th><th>Latency</th><th>Attempts</th></tr></thead>
            <tbody>
              {calls.rows.map((c) => (
                <Fragment key={c.call_id}>
                  <tr className="cursor-pointer" onClick={() => setOpen(open === c.call_id ? null : c.call_id)}>
                    <td className="font-mono text-[12px]">{c.call_id}</td>
                    <td><StatusBadge status={c.status} /></td>
                    <td className="font-bold">{c.score ?? c.decision ?? "—"}</td>
                    <td className="text-[12px]">{c.served_model || "—"} {c.model_mismatch && <Badge tone="warning">mismatch</Badge>}</td>
                    <td className="text-[12px]">{c.finish_reason || "—"}</td>
                    <td className="text-[12px]">{fmt(c.input_tokens, 0)}/{fmt(c.output_tokens, 0)} ({fmt(c.reasoning_tokens, 0)})</td>
                    <td className="text-[12px]">{c.latency_s == null ? "—" : `${fmt(c.latency_s, 2)} s`}</td>
                    <td className="text-[12px]">{c.n_attempts ?? "—"}</td>
                  </tr>
                  {open === c.call_id && (
                    <tr><td colSpan={8} className="bg-bg">
                      <pre className="whitespace-pre-wrap break-words text-[12px]">{JSON.stringify({ response_text: c.response_text, reason: c.reason, error: c.error, attempts: c.attempts, retried_without: c.retried_without, request_id: c.request_id }, null, 2)}</pre>
                    </td></tr>
                  )}
                </Fragment>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
      {cfg && <div className="mt-5"><Note>Prompt SHA-256 <span className="font-mono">{m.prompt_sha256.slice(0, 16)}…</span> · input file {cfg.input_file} (sha256 <span className="font-mono">{String(cfg.input_sha256).slice(0, 12)}…</span>) · BibAIFilter {m.tool.version} · Python {m.environment.python}. These are stored in the manifest so the run can be described and repeated exactly.</Note></div>}
    </>
  );
}
