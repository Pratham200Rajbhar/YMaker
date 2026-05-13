import { Check } from "lucide-react";
import type { WorkflowStage, VideoFormat } from "@/lib/types";
import { motion } from "framer-motion";

const DEFAULT_STEPS: { id: WorkflowStage; label: string; description: string }[] = [
  { id: "script", label: "Script", description: "AI script generation" },
  { id: "scenes", label: "Scenes", description: "Scene breakdown" },
  { id: "clips", label: "Clips", description: "Stock video selection" },
  { id: "voiceover", label: "Voiceover", description: "NVIDIA Magpie TTS" },
  { id: "render", label: "Final Video", description: "MP4 Rendering" },
];

const IMAGE_STORY_STEPS: { id: WorkflowStage; label: string; description: string }[] = [
  { id: "script", label: "Script", description: "AI script generation" },
  { id: "scenes", label: "Scenes", description: "Scene breakdown" },
  { id: "image_upload", label: "Image Prompts & Upload", description: "AI image prompts & upload" },
  { id: "voiceover", label: "Voiceover", description: "NVIDIA Magpie TTS" },
  { id: "render", label: "Final Video", description: "MP4 Rendering" },
];

export function StepSidebar({ 
  active, 
  video_format = "shorts",
  onStepClick
}: { 
  active: WorkflowStage; 
  video_format?: VideoFormat;
  onStepClick?: (stage: WorkflowStage) => void;
}) {
  const steps = video_format === "image_story" ? IMAGE_STORY_STEPS : DEFAULT_STEPS;
  const activeIndex = steps.findIndex((step) => step.id === active);

  return (
    <aside className="glass sticky top-6 rounded-xl border border-forge-border p-5 shadow-2xl">
      <div className="mb-6 flex items-center justify-between px-1">
        <div className="text-[10px] font-black uppercase tracking-[0.3em] text-zinc-500">
          Production Flow
        </div>
        <div className="flex items-center gap-1.5">
          <div className="h-1 w-1 rounded-full bg-forge-red animate-pulse" />
          <div className="text-[10px] font-black tracking-tighter text-zinc-400">
            {Math.round(((activeIndex + 1) / steps.length) * 100)}%
          </div>
        </div>
      </div>
      
      <div className="relative space-y-1">
        {/* Progress Line */}
        <div className="absolute left-[22px] top-5 bottom-5 w-[1px] bg-white/5" />
        <motion.div 
          className="absolute left-[22px] top-5 w-[1px] bg-gradient-to-b from-forge-red to-rose-500 shadow-[0_0_15px_rgba(244,63,94,0.3)]"
          initial={{ height: 0 }}
          animate={{ height: `${(activeIndex / (steps.length - 1)) * 100}%` }}
          transition={{ duration: 1, ease: [0.4, 0, 0.2, 1] }}
        />

        {steps.map((step, index) => {
          const done = index < activeIndex;
          const current = index === activeIndex;
          const clickable = done || current; // Can click past or current to re-activate

          return (
            <div
              key={step.id}
              onClick={() => clickable && onStepClick?.(step.id)}
              className={`relative z-10 flex items-start gap-4 rounded-xl px-3 py-3 transition-all duration-300 ${
                current
                  ? "bg-forge-red/10 ring-1 ring-forge-red/20 shadow-glow-red/5"
                  : clickable 
                    ? "hover:bg-white/[0.05] cursor-pointer group" 
                    : "opacity-40"
              }`}
            >
              <div className={`mt-1 flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full border transition-all duration-700 ${
                done ? "border-emerald-500/40 bg-emerald-500/5 group-hover:border-emerald-400" : 
                current ? "border-forge-red bg-forge-bg shadow-[0_0_12px_rgba(244,63,94,0.25)]" : 
                "border-white/5 bg-forge-bg"
              }`}>
                {done ? (
                  <Check className="h-2.5 w-2.5 text-emerald-400 group-hover:scale-110 transition-transform" />
                ) : (
                  <div className={`h-1 w-1 rounded-full transition-all duration-500 ${
                    current ? "bg-forge-red scale-125 shadow-[0_0_10px_rgba(244,63,94,0.6)]" : "bg-zinc-800"
                  }`} />
                )}
              </div>
              
              <div className="flex-1 overflow-hidden">
                <div className={`text-xs font-bold leading-tight tracking-tight transition-colors duration-300 ${
                  current ? "text-white" : done ? "text-zinc-400 group-hover:text-zinc-200" : "text-zinc-500"
                }`}>
                  {step.label}
                </div>
                <div className={`mt-0.5 truncate text-[10px] font-medium transition-colors duration-300 ${
                  current ? "text-zinc-400" : "text-zinc-600 group-hover:text-zinc-400"
                }`}>
                  {step.description}
                </div>
              </div>

              {current && (
                <motion.div 
                  layoutId="active-indicator"
                  className="mt-1.5 h-1.5 w-1.5 rounded-full bg-forge-red shadow-glow-red"
                  animate={{ 
                    opacity: [0.5, 1, 0.5],
                    scale: [0.9, 1.1, 0.9],
                    boxShadow: [
                      "0 0 10px rgba(244,63,94,0.3)",
                      "0 0 20px rgba(244,63,94,0.6)",
                      "0 0 10px rgba(244,63,94,0.3)"
                    ]
                  }}
                  transition={{ repeat: Infinity, duration: 2.5 }}
                />
              )}
            </div>
          );
        })}
      </div>
    </aside>
  );
}
