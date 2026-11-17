"use client";

import { ArrowUp, Folder, FolderPlus, Home, X } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Button, ErrorBox, inputCls } from "./ui";

type Listing = { path: string; parent: string | null; dirs: string[]; home: string; roots: string[] };

/** Browse folders on this computer (served by the local BibAIFilter server). */
export function FolderPicker({ open, start, title, onPick, onClose }: {
  open: boolean; start?: string; title?: string; onPick: (path: string) => void; onClose: () => void;
}) {
  const [ls, setLs] = useState<Listing | null>(null);
  const [newName, setNewName] = useState("");
  const [err, setErr] = useState<unknown>(null);
  const go = (path?: string) => {
    setErr(null);
    api.get<Listing>(`/api/fs/list${path ? `?path=${encodeURIComponent(path)}` : ""}`).then(setLs).catch(setErr);
  };
  useEffect(() => { if (open) go(start); }, [open, start]); // eslint-disable-line react-hooks/exhaustive-deps
  if (!open) return null;
  const sep = ls?.path.includes("\\") ? "\\" : "/";
  const join = (a: string, b: string) => (a.endsWith(sep) ? a + b : a + sep + b);

  async function mkdir() {
    if (!ls || !newName.trim()) return;
    try {
      const r = await api.post<{ path: string }>("/api/fs/mkdir", { path: join(ls.path, newName.trim()) });
      setNewName("");
      go(r.path);
    } catch (e) { setErr(e); }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-brand-950/40 p-4" onClick={onClose}>
      <div className="flex max-h-[80vh] w-full max-w-xl flex-col rounded-xl bg-white shadow-soft" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between border-b border-border px-4 py-3">
          <h3 className="text-[15px] font-bold">{title || "Choose a folder"}</h3>
          <button onClick={onClose} aria-label="Close"><X className="h-5 w-5 text-muted" /></button>
        </div>
        <div className="flex items-center gap-2 border-b border-border px-4 py-2">
          <Button size="sm" variant="ghost" onClick={() => ls?.parent && go(ls.parent)} disabled={!ls?.parent}><ArrowUp className="h-4 w-4" /></Button>
          <Button size="sm" variant="ghost" onClick={() => go(ls?.home)}><Home className="h-4 w-4" /></Button>
          {ls?.roots.map((r) => <Button key={r} size="sm" variant="ghost" onClick={() => go(r)}>{r}</Button>)}
          <input className={inputCls + " font-mono text-[12px]"} value={ls?.path || ""} onChange={(e) => setLs(ls && { ...ls, path: e.target.value })}
            onKeyDown={(e) => e.key === "Enter" && go((e.target as HTMLInputElement).value)} />
        </div>
        <div className="min-h-[220px] flex-1 overflow-auto px-2 py-2">
          <ErrorBox error={err} />
          {ls?.dirs.length === 0 && <p className="px-2 py-3 text-[13px] text-muted">No sub-folders.</p>}
          {ls?.dirs.map((d) => (
            <button key={d} onClick={() => go(join(ls.path, d))}
              className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-[13.5px] hover:bg-bg-soft">
              <Folder className="h-4 w-4 text-accent-600" />{d}
            </button>
          ))}
        </div>
        <div className="flex flex-wrap items-center gap-2 border-t border-border px-4 py-3">
          <input className={inputCls + " max-w-[200px]"} placeholder="new folder name" value={newName} onChange={(e) => setNewName(e.target.value)} />
          <Button size="sm" variant="outline" onClick={mkdir} disabled={!newName.trim()}><FolderPlus className="h-4 w-4" />Create</Button>
          <div className="flex-1" />
          <Button size="sm" variant="ghost" onClick={onClose}>Cancel</Button>
          <Button size="sm" variant="accent" onClick={() => ls && onPick(ls.path)} disabled={!ls}>Use this folder</Button>
        </div>
      </div>
    </div>
  );
}
