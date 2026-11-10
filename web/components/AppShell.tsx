"use client";

import clsx from "clsx";
import { BookOpen, GitCompare, KeyRound, LayoutDashboard, PlusCircle } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import React, { useEffect, useState } from "react";
import { api } from "@/lib/api";

const NAV = [
  { href: "/", label: "Runs", icon: LayoutDashboard },
  { href: "/new/", label: "New run", icon: PlusCircle },
  { href: "/compare/", label: "Compare", icon: GitCompare },
  { href: "/settings/", label: "Settings", icon: KeyRound },
  { href: "/guide/", label: "Guide", icon: BookOpen },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const path = usePathname() || "/";
  const [version, setVersion] = useState<string>("");
  const [offline, setOffline] = useState(false);
  useEffect(() => {
    api.get<{ version: string; codename: string }>("/api/health")
      .then((h) => setVersion(`v${h.version} “${h.codename}”`))
      .catch(() => setOffline(true));
  }, []);
  const norm = (p: string) => (p.endsWith("/") ? p : p + "/");
  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-30 border-b border-brand-950 bg-brand-900 text-white">
        <div className="mx-auto flex max-w-7xl items-center gap-6 px-5 py-2.5">
          <Link href="/" className="flex items-center gap-2.5">
            <span className="flex h-9 items-center rounded-md bg-white px-2">
              <img src="/logo.webp" alt="BibAIFilter" className="h-7 w-auto" />
            </span>
            <span className="hidden rounded-full bg-sun px-2 py-0.5 text-[11px] font-extrabold text-brand-950 sm:inline">2.0</span>
          </Link>
          <nav className="flex flex-1 items-center gap-1 overflow-x-auto">
            {NAV.map(({ href, label, icon: Icon }) => {
              const active = href === "/" ? path === "/" : norm(path).startsWith(href);
              return (
                <Link key={href} href={href}
                  className={clsx("flex items-center gap-1.5 whitespace-nowrap rounded-md px-3 py-1.5 text-[13.5px] font-semibold transition",
                    active ? "bg-white/15 text-white" : "text-brand-100 hover:bg-white/10 hover:text-white")}>
                  <Icon className="h-4 w-4" />{label}
                </Link>
              );
            })}
          </nav>
          <span className="hidden text-[12px] text-brand-200 md:inline">{version}</span>
        </div>
      </header>
      {offline && (
        <div className="bg-danger px-5 py-2 text-center text-[13px] font-semibold text-white">
          Cannot reach the BibAIFilter server. Start it with <code className="rounded bg-white/20 px-1">bibaifilter</code> and reload.
        </div>
      )}
      <main className="mx-auto max-w-7xl px-5 py-6">{children}</main>
      <footer className="mx-auto max-w-7xl px-5 pb-8 pt-2 text-[12px] text-muted">
        BibAIFilter is open source (GPL-3.0). Every provider call is logged in the run folder; API keys stay on this computer.
      </footer>
    </div>
  );
}

export function PageTitle({ title, subtitle, actions }: { title: string; subtitle?: React.ReactNode; actions?: React.ReactNode }) {
  return (
    <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-2xl font-extrabold tracking-tight text-ink">{title}</h1>
        {subtitle && <p className="mt-1 max-w-3xl text-[14px] text-muted">{subtitle}</p>}
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  );
}
