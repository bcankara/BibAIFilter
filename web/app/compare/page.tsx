"use client";

import { useEffect, useState } from "react";
import { PageTitle } from "@/components/AppShell";
import { Badge, Button, Card, ErrorBox, Note, fmt } from "@/components/ui";
import { api, RunListItem } from "@/lib/api";

export default function Compare() {
  const [runs, setRuns] = useState<RunListItem[]>([]);
  const [sel, setSel] = useState<string[]>([]);
  const [res, setRes] = useState<any>(null);
  const [err, setErr] = useState<unknown>(null);
  useEffect(() => { api.get<RunListItem[]>("/api/runs").then(setRuns).catch(setErr); }, []);
  const toggle = (id: string) => setSel((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]));
  const go = () => api.post("/api/compare", { run_ids: sel }).then(setRes).catch(setErr);

  return (
    <>
      <PageTitle title="Compare runs" subtitle="Rank correlation of record means between runs on the same records, and a check for identical score vectors (which can indicate that two model names were served by the same model)." />
      <ErrorBox error={err} />
      <Card title="Choose runs" actions={<Button size="sm" onClick={go} disabled={sel.length < 2}>Compare {sel.length || ""}</Button>}>
        <div className="grid gap-1.5 md:grid-cols-2">
          {runs.map((r) => (
            <label key={r.run_id} className="flex items-center gap-2 rounded-md px-2 py-1.5 text-[13px] hover:bg-bg-soft">
              <input type="checkbox" checked={sel.includes(r.run_id)} onChange={() => toggle(r.run_id)} />
              <span className="font-semibold">{r.name}</span>
              <span className="text-muted">{r.n_records} records · {r.state?.status}</span>
            </label>
          ))}
        </div>
      </Card>
      {res && (
        <Card className="mt-5" title="Spearman correlation of record means">
          {!res.same_record_count && <Note tone="warning">The runs do not cover the same number of records; only identical record sets can be compared.</Note>}
          {res.spearman_matrix && (
            <div className="-mx-5 -my-4 overflow-auto">
              <table className="data">
                <thead><tr><th>Run</th>{res.runs.map((r: string, i: number) => <th key={r} className="text-center" title={r}>{i + 1}</th>)}</tr></thead>
                <tbody>
                  {res.runs.map((a: string, i: number) => (
                    <tr key={a}><td className="whitespace-nowrap font-semibold">{i + 1}. {a}</td>
                      {res.runs.map((b: string) => {
                        const v = res.spearman_matrix[a][b];
                        const bg = v == null ? "transparent" : `rgba(43,107,187,${Math.max(0, Math.min(1, (v - 0.6) / 0.4)) * 0.55})`;
                        return <td key={b} className="text-center text-[11.5px]" style={{ background: bg }}>{fmt(v, 2)}</td>;
                      })}</tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <div className="mt-6">
            {res.identical_vectors?.length
              ? <Note tone="warning">Identical score vectors: {res.identical_vectors.map((p: string[]) => <Badge key={p.join()} tone="warning">{p[0]} = {p[1]}</Badge>)}. Check the served model of each call in the run logs.</Note>
              : <Note>No pair of runs has identical score vectors.</Note>}
          </div>
        </Card>
      )}
    </>
  );
}
