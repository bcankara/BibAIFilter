"use client";

import { ExternalLink, FolderOpen } from "lucide-react";
import { FolderPicker } from "@/components/FolderPicker";
import { useEffect, useState } from "react";
import { PageTitle } from "@/components/AppShell";
import { Badge, Button, Card, ErrorBox, Note, inputCls } from "@/components/ui";
import { api, Preset, Provider, Workspace } from "@/lib/api";

export default function Settings() {
  const [providers, setProviders] = useState<Provider[]>([]);
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [msg, setMsg] = useState<string>("");
  const [err, setErr] = useState<unknown>(null);
  const [ws, setWs] = useState<Workspace | null>(null);
  const [picking, setPicking] = useState(false);
  const [prompts, setPrompts] = useState<(Preset & { builtin: boolean; sha256?: string; saved_at?: string })[]>([]);
  const load = () => {
    api.get<any[]>("/api/presets").then((p) => setPrompts(p.filter((x) => !x.builtin))).catch(setErr);
    api.get<Provider[]>("/api/providers").then(setProviders).catch(setErr);
    api.get<Workspace>("/api/workspace").then(setWs).catch(setErr);
  };
  useEffect(() => { load(); }, []);
  async function setWorkspace(path: string | null) {
    try {
      await api.put("/api/workspace", { path });
      setPicking(false);
      setMsg(path ? `Workspace set to ${path}.` : "Workspace reset to the default folder.");
      load();
    } catch (e) { setErr(e); }
  }

  async function save(id: string) {
    try {
      const r = await api.put<{ stored_in: string }>(`/api/keys/${id}`, { key: draft[id] || "" });
      setMsg(`Key for ${id} stored in ${r.stored_in}.`);
      setDraft({ ...draft, [id]: "" });
      load();
    } catch (e) { setErr(e); }
  }
  async function remove(id: string) {
    await api.del(`/api/keys/${id}`).catch(setErr);
    load();
  }

  return (
    <>
      <PageTitle title="Settings" subtitle="Where your work is saved, and the API keys of the providers you use." />
      <ErrorBox error={err} />
      {msg && <div className="mb-4"><Note>{msg}</Note></div>}
      <Card className="mb-5" title="Workspace folder" subtitle="Uploaded files, run folders (manifest and full call log) and exported results are kept here."
        actions={<>
          {ws?.source === "chosen in settings" && <Button size="sm" variant="ghost" onClick={() => setWorkspace(null)}>Reset to default</Button>}
          <Button size="sm" onClick={() => setPicking(true)} disabled={ws?.source?.startsWith("environment")}><FolderOpen className="h-4 w-4" />Change…</Button>
        </>}>
        <div className="font-mono text-[13px]">{ws?.path}</div>
        <div className="mt-1 text-[12px] text-muted">{ws?.source === "default" ? "Default location." : ws?.source === "chosen in settings" ? "Chosen by you." : `Set by ${ws?.source}; change it there.`} Results of each run are also copied to <span className="font-mono">{ws?.exports}</span> unless you choose another folder when starting the run.</div>
      </Card>
      <FolderPicker open={picking} start={ws?.path} title="Choose the workspace folder" onPick={(p) => setWorkspace(p)} onClose={() => setPicking(false)} />
      <Card className="mb-5" title="Saved prompt templates" subtitle="Templates you saved from a new run. They appear next to the built-in templates; the template used by each run is also stored in that run's manifest.">
        {prompts.length === 0 ? <p className="text-[13px] text-muted">None yet. Edit a template in “New run” and choose “Save as template…”.</p> : (
          <table className="data"><tbody>{prompts.map((p) => (
            <tr key={p.id}><td className="font-semibold">{p.label}</td><td>{p.task === "score" ? "relevance score" : "eligibility"}</td>
              <td className="font-mono text-[11.5px] text-muted">sha256 {p.sha256?.slice(0, 12)}…</td><td className="text-muted">{p.saved_at}</td>
              <td><Button size="sm" variant="ghost" onClick={() => api.del(`/api/prompts/${p.id}`).then(load).catch(setErr)}>Delete</Button></td></tr>
          ))}</tbody></table>
        )}
      </Card>
      <h2 className="mb-1 mt-2 text-[17px] font-extrabold">API keys</h2>
      <p className="mb-4 max-w-3xl text-[13px] text-muted">Keys are kept on this computer: in the operating-system keyring when available, otherwise in a file readable only by you. Environment variables (e.g. OPENAI_API_KEY) take precedence. Keys never appear in run folders, logs or exports.</p>
      <div className="grid gap-4 md:grid-cols-2">
        {providers.map((p) => (
          <Card key={p.id} title={p.label} actions={p.key.configured ? <Badge tone="success">set · {p.key.source}</Badge> : (p.id === "ollama" ? <Badge>no key needed</Badge> : <Badge tone="warning">not set</Badge>)}>
            {p.id === "ollama" ? (
              <p className="text-[13px] text-muted">Install Ollama, pull a model (e.g. <code>ollama pull qwen3:8b</code>) and choose provider “Ollama” in a new run. Nothing leaves your computer, and an open-weight model pinned by its digest gives fully repeatable runs.</p>
            ) : (
              <div className="flex gap-2">
                <input type="password" className={inputCls} placeholder={p.key.hint || `paste key${p.key_env ? ` (or set ${p.key_env})` : ""}`}
                  value={draft[p.id] || ""} onChange={(e) => setDraft({ ...draft, [p.id]: e.target.value })} autoComplete="off" />
                <Button size="sm" onClick={() => save(p.id)} disabled={!draft[p.id]}>Save</Button>
                {p.key.configured && !p.key.source?.startsWith("environment") && <Button size="sm" variant="ghost" onClick={() => remove(p.id)}>Remove</Button>}
              </div>
            )}
            {p.key_url && <a className="mt-2 inline-flex items-center gap-1 text-[12.5px] text-accent-700 hover:underline" href={p.key_url} target="_blank" rel="noreferrer">Get a key <ExternalLink className="h-3 w-3" /></a>}
          </Card>
        ))}
      </div>
    </>
  );
}
