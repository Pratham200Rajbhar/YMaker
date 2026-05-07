import { Check, Circle, Lock } from "lucide-react";
import type { WorkflowStage } from "@/lib/types";
import { motion } from "framer-motion";

const steps: { id: WorkflowStage; label: string; description: string }[] = [
  { id: "script", label: "Script", description: "AI script generation" },
  { id: "scenes", label: "Scenes", description: "Scene breakdown" },
  { id: "clips", label: "Clips", description: "Stock video selection" },
  { id: "voiceover", label: "Voiceover", description: "NVIDIA Magpie TTS" },
  { id: "render", label: "Final Video", description: "MP4 Rendering" },
];

export function StepSidebar({ active }: { active: WorkflowStage }) {
  const activeIndex = steps.findIndex((step) => step.id === active);

  return (
    <aside className="glass sticky top-6 rounded-xl border border-forge-border p-5 shadow-2xl">
      <div className="mb-6 flex items-center justify-between">
        <div className="text-[10px] font-black uppercase tracking-[0.2em] text-zinc-500">
          Production Flow
        </div>
        <div className="text-[10px] font-black text-forge-red">
          {Math.round(((activeIndex + 1) / steps.length) * 100)}%
        </div>
      </div>
      
      <div className="relative space-y-2">
        {/* Progress Line */}
        <div className="absolute left-5 top-4 bottom-4 w-[1px] bg-zinc-800" />
        <motion.div 
          className="absolute left-5 top-4 w-[1px] bg-forge-red shadow-[0_0_10px_rgba(244,63,94,0.5)]"
          initial={{ height: 0 }}
          animate={{ height: `${(activeIndex / (steps.length - 1)) * 100}%` }}
          transition={{ duration: 0.5, ease: "easeInOut" }}
        />

        {steps.map((step, index) => {
          const done = index < activeIndex;
          const current = index === activeIndex;
          const future = index > activeIndex;

          return (
            <div
              key={step.id}
              className={`relative z-10 flex items-start gap-4 rounded-xl px-3 py-4 transition-all duration-300 ${
                current
                  ? "bg-forge-red/10 ring-1 ring-forge-red/20"
                  : "hover:bg-white/[0.02]"
              }`}
            >
              <div className={`mt-0.5 flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full border transition-all duration-300 ${
                done ? "border-emerald-500 bg-emerald-500/10" : 
                current ? "border-forge-red bg-forge-bg shadow-glow-red" : 
                "border-zinc-700 bg-forge-bg"
              }`}>
                {done ? (
                  <Check className="h-3 w-3 text-emerald-400" />
                ) : (
                  <div className={`h-1.5 w-1.5 rounded-full ${current ? "bg-forge-red animate-pulse" : "bg-zinc-800"}`} />
                )}
              </div>
              
              <div className="flex-1 overflow-hidden">
                <div className={`text-xs font-bold leading-tight tracking-tight transition-colors ${
                  current ? "text-white" : done ? "text-zinc-400" : "text-zinc-600"
                }`}>
                  {step.label}
                </div>
                <div className={`mt-1 truncate text-[10px] font-medium transition-colors ${
                  current ? "text-zinc-400" : "text-zinc-700"
                }`}>
                  {step.description}
                </div>
              </div>

              {current && (
                <motion.div 
                  layoutId="active-indicator"
                  className="ml-auto h-1 w-1 rounded-full bg-forge-red shadow-glow-red"
                />
              )}
            </div>
          );
        })}
      </div>
    </aside>
  );
}
