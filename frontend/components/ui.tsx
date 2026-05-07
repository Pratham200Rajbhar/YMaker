import { Loader2 } from "lucide-react";
import type { ButtonHTMLAttributes, ReactNode } from "react";

export function Button({ children, className = "", busy = false, ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { busy?: boolean }) {
  return (
    <button
      className={`focus-ring inline-flex min-h-11 items-center justify-center gap-2 rounded-lg px-5 py-2.5 text-sm font-bold tracking-tight shadow-glow-red/10 transition-all duration-200 active:scale-95 disabled:cursor-not-allowed disabled:opacity-50 ${className}`}
      disabled={busy || props.disabled}
      {...props}
    >
      {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
      {children}
    </button>
  );
}

export function Badge({ children, tone = "default", className = "" }: { children: ReactNode; tone?: "default" | "red" | "green" | "accent"; className?: string }) {
  const tones = {
    red: "border-forge-red/30 bg-forge-red/10 text-forge-red shadow-glow-red/20",
    green: "border-emerald-500/30 bg-emerald-500/10 text-emerald-400",
    accent: "border-forge-accent/30 bg-forge-accent/10 text-forge-accent shadow-glow-accent/20",
    default: "border-white/10 bg-white/5 text-zinc-400"
  };
  const styles = tones[tone] || tones.default;
  return <span className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider ${styles} ${className}`}>{children}</span>;
}

export function Panel({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <section className={`glass rounded-xl border border-forge-border p-6 shadow-2xl ${className}`}>{children}</section>;
}

export function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="block space-y-2">
      <span className="text-xs font-semibold uppercase tracking-wide text-zinc-400">{label}</span>
      {children}
    </label>
  );
}

export const inputClass = "focus-ring w-full rounded-lg border border-forge-border bg-forge-panel px-4 py-3 text-sm text-white transition-all placeholder:text-zinc-600 focus:border-forge-red/40 focus:bg-forge-panel2";

export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse rounded-lg bg-white/5 ${className}`} />;
}
