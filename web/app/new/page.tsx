"use client";

import clsx from "clsx";
import { CheckCircle2, Eye, FileUp, FolderOpen, PlayCircle, Plug, Save } from "lucide-react";
import { FolderPicker } from "@/components/FolderPicker";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { PageTitle } from "@/components/AppShell";
import { Badge, Button, Card, ErrorBox, Field, Note, Stat, fmt, inputCls } from "@/components/ui";
import { api, Catalog, Dataset, ModelSpec, Preset, Provider, Workspace } from "@/lib/api";

const FIELD_LABELS: Record<string, string> = {
  title: "Title", abstract: "Abstract", keywords: "Keywords", year: "Year", doi: "DOI", authors: "Authors",
  source: "Source / journal", categories: "Subject categories",
  label: "Include/exclude label (optional, for recall & WSS)", reference_score: "Reference score (optional, e.g. human mean)",
};

type MappingInfo = { n_records: number; n_empty: number; n_without_abstract: number; n_labelled: number; n_label_include: number; n_reference: number };

function Step({ n, title, done, children }: { n: number; title: string; done?: boolean; children: React.ReactNode }) {
  return (
    <Card title={<span className="flex items-center gap-2">
      <span className={clsx("flex h-6 w-6 items-center justify-center rounded-full text-[12px] font-bold",
        done ? "bg-success text-white" : "bg-brand-900 text-white")}>{done ? "✓" : n}</span>{title}</span>}>
      {children}
    </Card>
  );
}

export default function NewRun() {
  const router = useRouter();
  const [providers, setProviders] = useState<Provider[]>([]);
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [presets, setPresets] = useState<Preset[]>([]);
  const [ds, setDs] = useState<Dataset | null>(null);
  const [mapping, setMapping] = useState<Record<string, string | null>>({});
  const [minfo, setMinfo] = useState<MappingInfo | null>(null);
  const [uploading, setUploading] = useState(false);
  const [err, setErr] = useState<unknown>(null);

  const [task, setTask] = useState<"score" | "eligibility">("score");
  const [presetId, setPresetId] = useState("score-v2");
  const [template, setTemplate] = useState("");
  const [topic, setTopic] = useState("");
  const [criteria, setCriteria] = useState("");

  const [provider, setProvider] = useState("openai");
  const [model, setModel] = useState("");
  const [customModel, setCustomModel] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [temperature, setTemperature] = useState<string>("0");
  const [reasoning, setReasoning] = useState<string>("");
  const [maxTokens, setMaxTokens] = useState<string>("");
  const [structured, setStructured] = useState(true);
  const [repetitions, setRepetitions] = useState(3);
  const [shuffle, setShuffle] = useState(true);
  const [seed, setSeed] = useState(20261110);
  const [threshold, setThreshold] = useState(4);
  const [concurrency, setConcurrency] = useState(2);
  const [maxCost, setMaxCost] = useState<string>("5");
  const [maxRecords, setMaxRecords] = useState<string>("");
  const [name, setName] = useState("");
  const [outputDir, setOutputDir] = useState("");
  const [ws, setWs] = useState<Workspace | null>(null);
  const [picking, setPicking] = useState(false);

  const [estimate, setEstimate] = useState<any>(null);
  const [preview, setPreview] = useState<any>(null);
  const [previewIdx, setPreviewIdx] = useState(0);
  const [check, setCheck] = useState<any>(null);
  const [checking, setChecking] = useState(false);
  const [starting, setStarting] = useState(false);

  useEffect(() => {
    api.get<Provider[]>("/api/providers").then(setProviders).catch(setErr);
    api.get<Catalog>("/api/catalog").then(setCatalog).catch(setErr);
    api.get<Workspace>("/api/workspace").then(setWs).catch(setErr);
    api.get<Preset[]>("/api/presets").then((p) => {
      setPresets(p);
      const d = p.find((x) => x.id === "score-v2");
      if (d) setTemplate(d.template);
    }).catch(setErr);
  }, []);

  const models = useMemo(() => (catalog?.models || []).filter((m) => m.provider === provider), [catalog, provider]);
  const modelId = model === "__custom" ? customModel.trim() : model;
  const spec: ModelSpec | undefined = models.find((m) => m.id === modelId);

  useEffect(() => {
    const first = models.find((m) => m.status === "current") || models[0];
    setModel(first ? first.id : "__custom");
    setBaseUrl(provider === "ollama" ? "http://localhost:11434/v1" : "");
  }, [provider, catalog]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    setReasoning(spec?.recommended_reasoning || "");
    setMaxTokens("");
  }, [modelId]); // eslint-disable-line react-hooks/exhaustive-deps

  const choosePreset = (id: string) => {
    const p = presets.find((x) => x.id === id);
    if (!p) return;
    setPresetId(id);
    setTask(p.task);
    setTemplate(p.template);
  };

  async function onFile(f: File | undefined) {
    if (!f) return;
    setErr(null); setUploading(true); setMinfo(null);
    try {
      const d = await api.upload<Dataset>("/api/datasets", f);
      setDs(d); setMapping(d.mapping);
      setMinfo(await api.post<MappingInfo>(`/api/datasets/${d.id}/mapping`, { mapping: d.mapping }));
    } catch (e) { setErr(e); } finally { setUploading(false); }
  }

  async function updateMapping(field: string, col: string) {
    if (!ds) return;
    const m = { ...mapping, [field]: col || null };
    setMapping(m);
    try { setMinfo(await api.post<MappingInfo>(`/api/datasets/${ds.id}/mapping`, { mapping: m })); } catch (e) { setErr(e); }
  }

  const payload = () => ({
    name, dataset_id: ds?.id, mapping, task, preset_id: presetId, template, topic, criteria, provider,
    model: modelId, base_url: baseUrl || null,
    settings: {
      temperature: temperature === "" ? null : Number(temperature),
      reasoning: reasoning || null,
      max_output_tokens: maxTokens ? Number(maxTokens) : null,
      structured, seed,
    },
    repetitions, shuffle, seed, threshold, concurrency,
    max_cost_usd: maxCost ? Number(maxCost) : null, max_records: maxRecords ? Number(maxRecords) : null,
    output_dir: outputDir || null,
  });

  const ready = !!ds && !!topic.trim() && !!modelId && !!name.trim() && (task === "score" || !!criteria.trim());

  const payloadKey = JSON.stringify(payload());
  useEffect(() => {
    if (!ready) { setEstimate(null); return; }
    const t = setTimeout(() => api.post("/api/estimate", JSON.parse(payloadKey)).then(setEstimate).catch(() => setEstimate(null)), 400);
    return () => clearTimeout(t);
  }, [payloadKey, ready]);

  async function loadPreview(idx?: number) {
    if (!ds) return;
    const p = payload();
    try {
      setPreview(await api.post("/api/preview", { ...p, record_index: typeof idx === "number" ? idx : previewIdx }));
    } catch (e) { setErr(e); }
  }
  useEffect(() => { if (preview) loadPreview(previewIdx); }, [previewIdx]); // eslint-disable-line react-hooks/exhaustive-deps

  async function savePrompt() {
    const label = window.prompt("Name for this template (it will be listed with the built-in templates):");
    if (!label) return;
    try {
      const saved = await api.post<Preset>("/api/prompts", { label, task, template });
      const list = await api.get<Preset[]>("/api/presets");
      setPresets(list);
      setPresetId(saved.id);
    } catch (e) { setErr(e); }
  }

  async function runCheck() {
    setChecking(true); setCheck(null);
    try { setCheck(await api.post("/api/check", { provider, model: modelId, base_url: baseUrl || null })); }
    catch (e) { setCheck({ ok: false, error: e instanceof Error ? e.message : String(e) }); }
    finally { setChecking(false); }
  }

  async function start() {
    setStarting(true); setErr(null);
    try {
      const r = await api.post<{ run_id: string }>("/api/runs", payload());
      router.push(`/run/?id=${r.run_id}`);
    } catch (e) { setErr(e); setStarting(false); }
  }

  const prov = providers.find((p) => p.id === provider);
  const tempNote = spec && {
    supported: "Sent as set.",
    reasoning_off_only: "Sent only when reasoning is off (set reasoning to “none”); otherwise omitted, as the provider requires.",
    ignored: "This model ignores temperature; it will not be sent.",
    unsupported: "This model rejects temperature; it will not be sent.",
  }[spec.temperature];

  return (
    <>
      <PageTitle title="New run" subtitle="Four steps: records, task, model, review. Nothing is sent to a provider until you press Start." />
      <div className="grid gap-5">
        <Step n={1} title="Records" done={!!minfo}>
          <label className={clsx("flex cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed px-6 py-7 text-center transition",
            ds ? "border-success/40 bg-success-soft/30" : "border-border hover:border-accent-400 hover:bg-accent-50")}>
            <FileUp className="h-7 w-7 text-accent-600" />
            <span className="text-sm font-semibold">{ds ? ds.file : uploading ? "Reading…" : "Choose a file"}</span>
            <span className="text-[12px] text-muted">Excel (.xlsx, .xls), CSV/TSV (Scopus export), RIS, BibTeX, Web of Science plain text</span>
            <input type="file" className="hidden" accept=".xlsx,.xls,.xlsm,.csv,.tsv,.txt,.ris,.bib,.bibtex"
              onChange={(e) => onFile(e.target.files?.[0])} />
          </label>
          {ds && (
            <div className="mt-4 grid gap-4 md:grid-cols-[1fr_280px]">
              <div className="grid gap-3 sm:grid-cols-2">
                {Object.keys(FIELD_LABELS).map((f) => (
                  <Field key={f} label={FIELD_LABELS[f]}>
                    <select className={inputCls} value={mapping[f] || ""} onChange={(e) => updateMapping(f, e.target.value)}>
                      <option value="">— not used —</option>
                      {ds.columns.map((c) => <option key={c} value={c}>{c}</option>)}
                    </select>
                  </Field>
                ))}
              </div>
              {minfo && (
                <div className="grid content-start gap-2">
                  <Stat label="Records" value={minfo.n_records} sub={`${ds.format} · sha256 ${ds.sha256.slice(0, 10)}…`} />
                  <Stat label="Without abstract" value={minfo.n_without_abstract}
                    sub={minfo.n_empty ? `${minfo.n_empty} with neither title nor abstract (skipped)` : undefined} />
                  <Stat label="Labelled" value={minfo.n_labelled}
                    sub={minfo.n_labelled ? `${minfo.n_label_include} included → recall, WSS@95 will be computed` : "optional"} />
                  {minfo.n_reference > 0 && <Stat label="Reference scores" value={minfo.n_reference} />}
                </div>
              )}
            </div>
          )}
        </Step>

        <Step n={2} title="Task and prompt" done={!!topic.trim() && (task === "score" || !!criteria.trim())}>
          <div className="grid gap-3 md:grid-cols-3">
            {presets.map((p) => (
              <button key={p.id} type="button" onClick={() => choosePreset(p.id)}
                className={clsx("rounded-lg border px-3.5 py-3 text-left transition",
                  presetId === p.id ? "border-accent-500 bg-accent-50 ring-2 ring-accent-100" : "border-border hover:bg-bg-soft")}>
                <div className="text-[13.5px] font-bold">{p.label}</div>
                <div className="mt-0.5 text-[12px] text-muted">{p.description}</div>
              </button>
            ))}
          </div>
          <div className="mt-4 grid gap-4 md:grid-cols-2">
            <Field label="Topic" hint="Inserted for {TOPIC}. It can be a whole research question — the model is not limited to keyword matching.">
              <textarea className={inputCls} rows={3} value={topic} onChange={(e) => setTopic(e.target.value)}
                placeholder="e.g. Generative AI feedback and L2 writing self-efficacy in secondary education" />
            </Field>
            {task === "eligibility" ? (
              <Field label="Eligibility criteria" hint="Inserted for {CRITERIA}. One criterion per line works best.">
                <textarea className={inputCls} rows={5} value={criteria} onChange={(e) => setCriteria(e.target.value)}
                  placeholder={"Population: secondary-school students\nIntervention: generative-AI feedback on writing\nDesign: empirical (experimental or quasi-experimental)\nExclude: reviews, editorials, conference abstracts"} />
              </Field>
            ) : (
              <Field label="Relevance threshold" hint="A record counts as relevant when its mean score is at or above this value (used for recall/precision).">
                <input type="number" min={1} max={7} className={inputCls} value={threshold} onChange={(e) => setThreshold(Number(e.target.value))} />
              </Field>
            )}
          </div>
          <div className="mt-4 rounded-lg border border-border bg-bg px-3.5 py-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <div className="text-[13.5px] font-bold">Prompt template</div>
                <p className="text-[12px] text-muted">Review and edit before starting. Placeholders: {"{TOPIC} {CRITERIA} {TITLE} {ABSTRACT} {KEYWORDS} {CATEGORIES}"}. The template text and its SHA-256 are stored with the run; report them if you change the default.</p>
              </div>
              <div className="flex gap-2">
                <Button size="sm" variant="outline" onClick={savePrompt} disabled={!template.trim()}><Save className="h-4 w-4" />Save as template…</Button>
                <Button size="sm" variant="outline" onClick={() => loadPreview()} disabled={!ds}><Eye className="h-4 w-4" />Preview the exact request</Button>
              </div>
            </div>
            <textarea className={clsx(inputCls, "mt-2 font-mono text-[12px]")} rows={14} value={template} onChange={(e) => setTemplate(e.target.value)} />
            {preview && (
              <div className="mt-3 grid gap-3 lg:grid-cols-2">
                <div>
                  <div className="mb-1 flex items-center gap-2 text-[12px] font-semibold text-muted">
                    Filled prompt for record
                    <select className="rounded border border-border px-1 py-0.5" value={previewIdx} onChange={(e) => { setPreviewIdx(Number(e.target.value)); }}>
                      {Array.from({ length: Math.min(minfo?.n_records || 1, 50) }, (_, i) => <option key={i} value={i}>#{i}</option>)}
                    </select>
                  </div>
                  <pre className="max-h-[360px] overflow-auto whitespace-pre-wrap rounded-lg border border-border bg-white p-3 text-[12px]">{preview.prompt}</pre>
                </div>
                <div>
                  <div className="mb-1 text-[12px] font-semibold text-muted">Request body sent to {prov?.label} (API key removed)</div>
                  <pre className="max-h-[360px] overflow-auto whitespace-pre-wrap rounded-lg border border-border bg-white p-3 text-[11.5px]">{JSON.stringify(preview.request_body, null, 2)}</pre>
                </div>
              </div>
            )}
          </div>
        </Step>

        <Step n={3} title="Model" done={!!modelId}>
          <div className="grid gap-4 md:grid-cols-4">
            <Field label="Provider" hint={prov && !prov.key.configured && !["ollama", "custom"].includes(provider)
              ? <span className="text-danger">No API key set — add one under Settings.</span>
              : prov?.key.source ? `Key from ${prov.key.source}` : undefined}>
              <select className={inputCls} value={provider} onChange={(e) => setProvider(e.target.value)}>
                {providers.map((p) => <option key={p.id} value={p.id}>{p.label}</option>)}
              </select>
            </Field>
            <Field className="md:col-span-2" label="Model" hint={spec ? <>{spec.status !== "current" && <Badge tone="warning">{spec.status}</Badge>} {spec.note}</> : "Any identifier the provider accepts."}>
              <select className={inputCls} value={model} onChange={(e) => setModel(e.target.value)}>
                {models.map((m) => <option key={m.id} value={m.id}>{m.label}{m.price_in != null ? ` — $${m.price_in}/${m.price_out} per 1M` : ""}</option>)}
                <option value="__custom">Other model id…</option>
              </select>
              {model === "__custom" && <input className={clsx(inputCls, "mt-2")} placeholder="model id" value={customModel} onChange={(e) => setCustomModel(e.target.value)} />}
            </Field>
            <Field label="Repetitions per record" hint="Repeated calls show how stable the answers are.">
              <input type="number" min={1} max={20} className={inputCls} value={repetitions} onChange={(e) => setRepetitions(Number(e.target.value))} />
            </Field>
            {(provider === "ollama" || provider === "custom") && (
              <Field className="md:col-span-2" label="Server address" hint="OpenAI-compatible endpoint">
                <input className={inputCls} value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} />
              </Field>
            )}
          </div>
          <div className="mt-3"><Note>
            BibAIFilter uses the most deterministic settings this model allows: temperature 0{spec && spec.temperature !== "supported" ? (spec.temperature === "reasoning_off_only" ? " (with reasoning off)" : " is requested but this model does not accept it, so it is not sent") : ""}, {spec?.reasoning_style ? <>reasoning “{reasoning || spec.recommended_reasoning || "provider default"}”</> : "no reasoning"}, and a JSON schema that allows only valid answers. What was actually sent is logged for every call. Answers can still vary between calls, which the repetitions measure.
          </Note></div>
          <details className="mt-3 rounded-lg border border-border px-3.5 py-2.5">
            <summary className="cursor-pointer text-[13px] font-semibold">Advanced settings</summary>
            <div className="mt-3 grid gap-4 md:grid-cols-4">
              <Field label="Temperature" hint={tempNote || "Empty = provider default."}>
                <input className={inputCls} value={temperature} onChange={(e) => setTemperature(e.target.value)} placeholder="provider default" />
              </Field>
              <Field label="Reasoning / thinking" hint={spec?.reasoning_style ? `Provider default: ${spec.default_reasoning || "not documented"}. Recommended: ${spec.recommended_reasoning || "—"}.` : "Not applicable to this model."}>
                <select className={inputCls} value={reasoning} onChange={(e) => setReasoning(e.target.value)} disabled={!spec?.reasoning_style}>
                  <option value="">provider default</option>
                  {(spec?.reasoning_levels || []).map((l) => <option key={l} value={l}>{l}</option>)}
                </select>
              </Field>
              <Field label="Max output tokens" hint={`Includes reasoning tokens. Default: ${spec?.default_max_output_tokens ?? "provider"}`}>
                <input className={inputCls} value={maxTokens} onChange={(e) => setMaxTokens(e.target.value)} placeholder={String(spec?.default_max_output_tokens ?? "")} />
              </Field>
              <Field label="Seed" hint="Record order (and the provider seed where supported)."><input type="number" className={inputCls} value={seed} onChange={(e) => setSeed(Number(e.target.value))} /></Field>
              <Field label="Cost cap (USD)" hint="The run stops when the estimated cost reaches this.">
                <input className={inputCls} value={maxCost} onChange={(e) => setMaxCost(e.target.value)} />
              </Field>
              <Field label="Parallel calls"><input type="number" min={1} max={16} className={inputCls} value={concurrency} onChange={(e) => setConcurrency(Number(e.target.value))} /></Field>
              <Field label="Only the first N records" hint="For a trial run."><input className={inputCls} value={maxRecords} onChange={(e) => setMaxRecords(e.target.value)} placeholder="all" /></Field>
              {provider !== "ollama" && provider !== "custom" && (
                <Field label="Server address" hint="Leave empty for the provider's API."><input className={inputCls} value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} placeholder="default" /></Field>
              )}
            </div>
            <div className="mt-3 flex flex-wrap gap-5 text-[13px]">
              <label className="flex items-center gap-2"><input type="checkbox" checked={structured} onChange={(e) => setStructured(e.target.checked)} />Structured output (JSON schema) where supported</label>
              <label className="flex items-center gap-2"><input type="checkbox" checked={shuffle} onChange={(e) => setShuffle(e.target.checked)} />New random record order in each repetition</label>
            </div>
          </details>
          <div className="mt-4 flex flex-wrap items-center gap-3">
            <Button variant="outline" size="sm" onClick={runCheck} loading={checking} disabled={!modelId}><Plug className="h-4 w-4" />Test this model</Button>
            {check && (check.ok
              ? <span className="text-[13px] text-success"><CheckCircle2 className="mr-1 inline h-4 w-4" />Answered “{check.answer}” in {check.latency_s}s · served model: <b>{check.served_model || "not reported"}</b>{check.model_mismatch && <Badge tone="warning">differs from requested</Badge>}</span>
              : <span className="text-[13px] text-danger">{check.error}</span>)}
          </div>
        </Step>

        <Step n={4} title="Review and start">
          {estimate ? (
            <div className="grid gap-3 sm:grid-cols-4">
              <Stat label="Calls" value={estimate.n_calls} sub={`${estimate.n_records} records × ${repetitions}`} />
              <Stat label="Prompt size" value={`~${estimate.input_tokens_per_call} tok`} sub="per call, estimated" />
              <Stat label="Estimated cost" value={estimate.price_known ? `$${fmt(estimate.cost_usd_estimate, 3)}` : "unknown"} sub={`list prices of ${estimate.catalog_date}`} />
              <Stat label="Cost cap" value={maxCost ? `$${maxCost}` : "none"} />
            </div>
          ) : <p className="text-[13px] text-muted">Complete steps 1–3 to see the estimate.</p>}
          <div className="mt-4 grid gap-4 md:grid-cols-2">
            <Field label="Run name" hint="Used for the result files, e.g. “teacher-education_gpt-6-luna”.">
              <input className={inputCls} value={name} onChange={(e) => setName(e.target.value)} placeholder="give the run a name" />
            </Field>
            <Field label="Save the results in" hint={outputDir ? "Excel, CSV, the full call log and the manifest are written here when the run ends." : `Default: ${ws?.exports || "workspace/exports"}/<run name>_<run id>`}>
              <div className="flex gap-2">
                <input className={inputCls + " font-mono text-[12px]"} value={outputDir} onChange={(e) => setOutputDir(e.target.value)} placeholder="default export folder" />
                <Button variant="outline" size="sm" onClick={() => setPicking(true)}><FolderOpen className="h-4 w-4" />Browse</Button>
              </div>
            </Field>
          </div>
          <FolderPicker open={picking} start={outputDir || ws?.exports} title="Save the results in…" onPick={(p) => { setOutputDir(p); setPicking(false); }} onClose={() => setPicking(false)} />
          <div className="mt-4 flex justify-end">
            <Button variant="accent" onClick={start} loading={starting} disabled={!ready}><PlayCircle className="h-4 w-4" />Start run</Button>
          </div>
          {!ready && ds && <p className="mt-2 text-right text-[12px] text-muted">To start: {[!topic.trim() && "a topic", task === "eligibility" && !criteria.trim() && "criteria", !modelId && "a model", !name.trim() && "a run name"].filter(Boolean).join(", ")}.</p>}
          <div className="mt-4"><Note>
            Titles, abstracts and keywords are sent to {prov?.label || "the provider"}. Check that the provider's terms and the
            licence of your database allow this, especially for unpublished records. Ollama keeps everything on this computer.
          </Note></div>
          <div className="mt-3"><ErrorBox error={err} /></div>
        </Step>
      </div>
    </>
  );
}
