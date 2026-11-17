"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { CheckCircle2, Circle, PlusCircle, RefreshCw } from "lucide-react";
import { PageTitle } from "@/components/AppShell";
import { Button, Card, ErrorBox, Note, StatusBadge, fmt } from "@/components/ui";
import { api, Provider, RunListItem, Workspace } from "@/lib/api";

export default function Home() {
  const [runs, setRuns] = useState<RunListItem[] | null>(null);
  const [err, setErr] = useState<unknown>(null);
  const [providers, setProviders] = useState<Provider[]>([]);
  const [ws, setWs] = useState<Workspace | null>(null);
  const load = () => api.get<RunListItem[]>("/api/runs").then(setRuns).catch(setErr);
  useEffect(() => {
    api.get<Provider[]>("/api/providers").then(setProviders).catch(() => undefined);
    api.get<Workspace>("/api/workspace").then(setWs).catch(() => undefined);
    load();
    const t = setInterval(load, 4000);
    return () => clearInterval(t);
  }, []);

  return (
    <>
      <PageTitle
        title="Runs"
        subtitle="Each run scores or screens a set of records with one model. Every call is logged with the parameters actually sent, the model that answered, tokens, time and cost."
        actions={<>
          <Button variant="outline" size="sm" onClick={load}><RefreshCw className="h-4 w-4" />Refresh</Button>
          <Link href="/new/"><Button variant="accent"><PlusCircle className="h-4 w-4" />New run</Button></Link>
        </>}
      />
      <ErrorBox error={err} />
      {runs && runs.length === 0 && (
        <Card title="Getting started" subtitle="Three steps before your first run.">
          <div className="grid gap-4 md:grid-cols-[1fr_200px]">
            <ol className="space-y-3 text-[14px]">
              {[
                { done: providers.some((p) => p.key.configured), title: "Add an API key", body: <>Open <Link className="font-semibold text-accent-700" href="/settings/">Settings</Link> and paste a key for OpenAI, Anthropic, Google, DeepSeek or OpenRouter — or install <b>Ollama</b> to use a local, free model (no key, nothing leaves your computer).</> },
                { done: ws?.source !== "default", title: "Choose where your work is saved (optional)", body: <>Now: <span className="font-mono text-[12.5px]">{ws?.path}</span>. Change it in <Link className="font-semibold text-accent-700" href="/settings/">Settings</Link>; each run can also save its results to a folder you pick.</> },
                { done: false, title: "Start a run", body: <>Upload an Excel, CSV, RIS, BibTeX or Web of Science file, describe your topic or your eligibility criteria, pick a model and name the run. Try a few records first.</> },
              ].map((s, i) => (
                <li key={i} className="flex gap-3">
                  {s.done ? <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-success" /> : <Circle className="mt-0.5 h-5 w-5 shrink-0 text-border" />}
                  <div><div className="font-semibold">{s.title}</div><div className="text-[13px] text-muted">{s.body}</div></div>
                </li>
              ))}
            </ol>
            <div className="flex flex-col items-center justify-center gap-3 rounded-xl bg-bg p-4">
              <img src="/icon.png" alt="" className="h-16 w-16" />
              <Link href="/new/"><Button variant="accent"><PlusCircle className="h-4 w-4" />New run</Button></Link>
            </div>
          </div>
        </Card>
      )}
      {runs && runs.length > 0 && (
        <Card className="overflow-hidden">
          <div className="-mx-5 -my-4 overflow-x-auto">
            <table className="data">
              <thead>
                <tr><th>Run</th><th>Task</th><th>Model</th><th>Records × reps</th><th>Progress</th><th>Valid calls</th><th>Status</th><th>Created</th></tr>
              </thead>
              <tbody>
                {runs.map((r) => {
                  const counts = r.counts || {};
                  const total = Object.values(counts).reduce((a, b) => a + b, 0);
                  const valid = (counts.ok || 0) + (counts.extracted || 0);
                  return (
                    <tr key={r.run_id}>
                      <td><Link className="font-semibold text-accent-700 hover:underline" href={`/run/?id=${r.run_id}`}>{r.name}</Link>
                        <div className="font-mono text-[11px] text-muted">{r.run_id}</div></td>
                      <td>{r.task === "score" ? "Relevance score" : "Eligibility"}</td>
                      <td><span className="text-muted">{r.provider}/</span>{r.model}</td>
                      <td>{r.n_records} × {r.repetitions}</td>
                      <td>{fmt(r.state?.done)} / {fmt(r.state?.total)}</td>
                      <td>{total ? `${valid}/${total}` : "—"}</td>
                      <td><StatusBadge status={r.state?.status} /></td>
                      <td className="whitespace-nowrap text-muted">{r.created_at?.slice(0, 16).replace("T", " ")}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Card>
      )}
      <div className="mt-5">
        <Note>
          BibAIFilter 2 never substitutes a default score: a failed, truncated or unparsable answer stays empty and is
          counted. The model is never switched behind your back — if the provider answers with a different model
          name, the call is flagged.
        </Note>
      </div>
    </>
  );
}
