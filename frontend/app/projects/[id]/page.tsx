"use client";

import Link from "next/link";
import { use, useCallback, useEffect, useState } from "react";
import {
  ArrowLeft,
  CheckCircle,
  ChevronDown,
  ChevronUp,
  Lock,
  RefreshCw,
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

import { api } from "@/lib/api";
import type { Project, WorkflowStage } from "@/lib/types";
import { StepSidebar } from "@/components/StepSidebar";
import { Badge, Button, Panel, Skeleton } from "@/components/ui";

import { ScriptStage } from "@/components/stages/ScriptStage";
import { ScenesStage } from "@/components/stages/ScenesStage";
import { ClipsStage } from "@/components/stages/ClipsStage";
import { VoiceStage } from "@/components/stages/VoiceStage";
import { RenderStage } from "@/components/stages/RenderStage";
import type { RunFn } from "@/components/stages/shared";

const STAGE_ORDER = ["script", "scenes", "clips", "voiceover", "render"] as const;
type Stage = (typeof STAGE_ORDER)[number];

export default function ProjectPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const projectId = Number(id);
  const [project, setProject] = useState<Project | null>(null);
  const [activeProviderLabel, setActiveProviderLabel] = useState<string>("");
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});

  const refresh = useCallback(async () => {
    const data = await api.getProject(projectId);
    setProject(data);
  }, [projectId]);

  useEffect(() => {
    refresh().catch((err) => setError(err.message));
    api.getSettings().then(s => setActiveProviderLabel(s.active_provider_label)).catch(console.error);
  }, [refresh]);

  useEffect(() => {
    const status = project?.render?.render_status;
    if (status !== "queued" && status !== "rendering") return;
    const timer = window.setInterval(() => refresh().catch(() => undefined), 2500);
    return () => window.clearInterval(timer);
  }, [project?.render?.render_status, refresh]);

  const run: RunFn = async (label, action) => {
    setBusy(label);
    setError("");
    try {
      setProject(await action());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Action failed");
    } finally {
      setBusy("");
    }
  };

  function toggleExpanded(stage: string) {
    setExpanded((prev) => ({ ...prev, [stage]: !prev[stage] }));
  }

  if (!project) {
    return <ProjectSkeleton />;
  }

  const activeIndex = STAGE_ORDER.indexOf(project.current_stage as Stage);

  return (
    <main className="min-h-screen bg-forge-bg selection:bg-forge-red/30">
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-[10%] left-[20%] w-[30%] h-[30%] bg-forge-red/5 rounded-full blur-[100px]" />
      </div>

      <div className="relative mx-auto max-w-7xl px-6 py-8">
        <header className="mb-8 flex flex-wrap items-end justify-between gap-6">
          <motion.div 
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            className="space-y-4"
          >
            <Link
              href="/"
              className="inline-flex items-center gap-2 text-[10px] font-black uppercase tracking-[0.2em] text-zinc-500 hover:text-white transition-colors"
            >
              <ArrowLeft className="h-3 w-3" />
              Back to Projects
            </Link>
            <h1 className="text-3xl font-black tracking-tight text-white md:text-4xl">
              {project.title}
            </h1>
            <div className="flex flex-wrap gap-2">
              <Badge tone="red" className="bg-forge-red/5 border-forge-red/20 px-3">
                {project.video_format === "shorts" ? "9:16 Vertical" : "16:9 Landscape"}
              </Badge>
              <Badge tone="accent">{project.current_stage}</Badge>
              <Badge tone={project.video_length === "auto" ? "red" : "default"} className="capitalize">
                {project.video_length === "auto" ? "✨ Auto Length" : `Length: ${project.video_length}`}
              </Badge>
              <Badge tone={project.status === "complete" ? "green" : "default"}>
                {project.status}
              </Badge>
              <Badge className="bg-white/5 border-white/10">{project.language}</Badge>
              <Badge tone={project.subtitles_enabled ? "accent" : "default"} className="bg-white/5 border-white/10">
                {project.subtitles_enabled ? `Subtitles: ${project.subtitle_language}` : "No Subtitles"}
              </Badge>
            </div>
          </motion.div>
          
          <motion.div
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
          >
            <Button
              className="glass border-forge-border text-zinc-200 hover:bg-forge-panel2/50"
              onClick={() => run("refresh", () => api.getProject(project.id))}
            >
              <RefreshCw className={`h-4 w-4 ${busy === "refresh" ? "animate-spin" : ""}`} />
              Sync State
            </Button>
          </motion.div>
        </header>

        <AnimatePresence>
          {error && (
            <motion.div 
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              className="mb-6 rounded-xl border border-forge-red/30 bg-forge-red/10 p-4 text-sm font-medium text-forge-red shadow-glow-red/10"
            >
              {error}
            </motion.div>
          )}
        </AnimatePresence>

        <div className="grid gap-8 lg:grid-cols-[280px_1fr]">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="space-y-6"
          >
            <StepSidebar active={project.current_stage as WorkflowStage} />
            
          </motion.div>

          <div className="space-y-6">
            {STAGE_ORDER.map((stage, index) => {
              const isPast = index < activeIndex;
              const isCurrent = index === activeIndex;
              const isFuture = index > activeIndex;

              if (isFuture) {
                return <LockedStage key={stage} stage={stage} />;
              }

              if (isPast) {
                const isOpen = expanded[stage] ?? false;
                return (
                  <motion.div
                    key={stage}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="rounded-xl border border-forge-border bg-forge-panel/40 overflow-hidden transition-all duration-300 hover:border-forge-border/80"
                  >
                    <button
                      className="w-full flex items-center justify-between px-6 py-5 text-left"
                      onClick={() => toggleExpanded(stage)}
                    >
                      <div className="flex items-center gap-4">
                        <div className="flex h-8 w-8 items-center justify-center rounded-full bg-emerald-500/10 border border-emerald-500/20">
                          <CheckCircle className="h-4 w-4 text-emerald-400" />
                        </div>
                        <div>
                          <span className="block text-sm font-bold text-zinc-200 capitalize tracking-tight">{stageName(stage)}</span>
                          <span className="text-[10px] font-black uppercase tracking-widest text-emerald-500/60">Stage Approved</span>
                        </div>
                      </div>
                      <div className="flex items-center gap-3">
                        <Badge tone="green" className="text-[9px]">Verified</Badge>
                        {isOpen ? (
                          <ChevronUp className="h-4 w-4 text-zinc-600" />
                        ) : (
                          <ChevronDown className="h-4 w-4 text-zinc-600" />
                        )}
                      </div>
                    </button>
                    <AnimatePresence>
                      {isOpen && (
                        <motion.div 
                          initial={{ opacity: 0, height: 0 }}
                          animate={{ opacity: 1, height: "auto" }}
                          exit={{ opacity: 0, height: 0 }}
                          className="border-t border-forge-border px-6 py-6 bg-forge-bg/30"
                        >
                          {renderStageContent(stage, project, busy, run, true, activeProviderLabel)}
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </motion.div>
                );
              }

              return (
                <motion.div
                  key={stage}
                  initial={{ opacity: 0, scale: 0.98 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ delay: 0.2 }}
                >
                  <Panel className="border-forge-red/20 shadow-glow-red/5">
                    {renderStageContent(stage, project, busy, run, false, activeProviderLabel)}
                  </Panel>
                </motion.div>
              );
            })}
          </div>
        </div>
      </div>
    </main>
  );
}

function renderStageContent(
  stage: string,
  project: Project,
  busy: string,
  run: RunFn,
  readOnly: boolean,
  providerLabel?: string
) {
  const props = { project, busy, run, readOnly, providerLabel };
  switch (stage) {
    case "script": return <ScriptStage {...props} />;
    case "scenes": return <ScenesStage {...props} />;
    case "clips": return <ClipsStage {...props} />;
    case "voiceover": return <VoiceStage {...props} />;
    case "render": return <RenderStage {...props} />;
    default: return null;
  }
}

function stageName(stage: string): string {
  const names: Record<string, string> = {
    script: "Script Design",
    scenes: "Visual Breakdown",
    clips: "Media Selection",
    voiceover: "Audio Forge",
    render: "Final Production",
  };
  return names[stage] ?? stage;
}

function LockedStage({ stage }: { stage: string }) {
  return (
    <div className="flex items-center gap-4 rounded-xl border border-forge-border bg-forge-panel/20 px-6 py-5 grayscale opacity-50">
      <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-zinc-900 border border-zinc-800">
        <Lock className="h-5 w-5 text-zinc-700" />
      </div>
      <div>
        <span className="block text-sm font-bold text-zinc-600 capitalize">{stageName(stage)}</span>
        <span className="text-[10px] font-black uppercase tracking-widest text-zinc-700">Locked Stage</span>
      </div>
    </div>
  );
}

function ProjectSkeleton() {
  return (
    <main className="min-h-screen bg-forge-bg p-8">
      <div className="mx-auto max-w-7xl space-y-8">
        <div className="space-y-4">
          <Skeleton className="h-4 w-24" />
          <Skeleton className="h-10 w-96" />
          <div className="flex gap-2">
            <Skeleton className="h-6 w-20 rounded-full" />
            <Skeleton className="h-6 w-20 rounded-full" />
            <Skeleton className="h-6 w-20 rounded-full" />
          </div>
        </div>
        <div className="grid gap-8 lg:grid-cols-[280px_1fr]">
          <Skeleton className="h-[600px] rounded-2xl" />
          <div className="space-y-6">
            {[1, 2, 3].map((i) => (
              <Skeleton key={i} className="h-48 rounded-2xl" />
            ))}
          </div>
        </div>
      </div>
    </main>
  );
}
