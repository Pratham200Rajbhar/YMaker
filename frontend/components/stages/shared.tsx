import { motion } from "framer-motion";
import { Sparkles, Wand2 } from "lucide-react";
import { Button } from "@/components/ui";
import type { Project, ProjectListItem, Script, Scene } from "@/lib/types";

export type RunFn = (label: string, action: () => Promise<Project>) => Promise<void>;

export type StageProps = {
  project: Project;
  busy: string;
  run: RunFn;
  readOnly: boolean;
};

export function StageHeader({ title, detail }: { title: string; detail?: string }) {
  return (
    <div className="mb-8">
      <div className="flex items-center gap-2 mb-1">
        <Sparkles className="h-4 w-4 text-forge-red" />
        <h2 className="text-2xl font-black tracking-tight text-white">{title}</h2>
      </div>
      {detail ? <p className="text-sm font-medium text-zinc-500 leading-relaxed max-w-2xl">{detail}</p> : null}
    </div>
  );
}

export function ActionRow({ children }: { children: React.ReactNode }) {
  return (
    <div className="mt-10 flex flex-wrap items-center gap-4 border-t border-forge-border pt-8">{children}</div>
  );
}

export function EmptyAction({
  label,
  busy,
  onClick,
}: {
  label: string;
  busy: boolean;
  onClick: () => void;
}) {
  return (
    <motion.div 
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="rounded-2xl border-2 border-dashed border-forge-border bg-white/[0.01] p-16 text-center"
    >
      <Button 
        className="mx-auto h-14 px-8 bg-gradient-to-r from-forge-red to-forge-red2 text-white shadow-2xl shadow-forge-red/30 hover:scale-105" 
        busy={busy} 
        onClick={onClick}
      >
        <Wand2 className="h-5 w-5" /> {label}
      </Button>
      <p className="mt-4 text-xs font-bold uppercase tracking-widest text-zinc-600">AI Assistance Required</p>
    </motion.div>
  );
}

export function MetaBox({ label, value }: { label: string; value: string | number | null }) {
  return (
    <div className="rounded-xl border border-forge-border bg-forge-bg/50 p-4 transition-colors hover:border-zinc-700">
      <div className="text-[10px] font-black uppercase tracking-[0.2em] text-zinc-500">{label}</div>
      <div className="mt-2 text-sm font-bold text-white leading-tight">{value || "Auto-detected"}</div>
    </div>
  );
}

export function stripScript(script: Script) {
  const { id: _id, version: _v, approved: _a, ...rest } = script;
  return rest;
}

export function updateSceneDraft(
  drafts: Scene[],
  setDrafts: (scenes: Scene[]) => void,
  index: number,
  patch: Partial<Scene>
) {
  setDrafts(drafts.map((scene, i) => (i === index ? { ...scene, ...patch } : scene)));
}
