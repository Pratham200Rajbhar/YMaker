import Image from "next/image";
import { Sparkles, Check } from "lucide-react";
import { motion } from "framer-motion";
import { api } from "@/lib/api";
import { Button, Badge } from "@/components/ui";
import { StageProps, StageHeader, EmptyAction, ActionRow } from "./shared";

export function ClipsStage({ project, busy, run, readOnly }: StageProps) {
  const hasClips = project.scenes.some((scene) => scene.clips.length > 0);

  if (readOnly) {
    const selectedCount = project.scenes.filter((s) =>
      s.clips.some((c) => c.selected)
    ).length;
    return (
      <div className="flex items-center gap-4">
        <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-emerald-500/10 border border-emerald-500/20">
          <Sparkles className="h-6 w-6 text-emerald-400" />
        </div>
        <div>
          <p className="text-sm font-bold text-zinc-200">Media Assets Selected</p>
          <p className="text-xs text-zinc-500">{selectedCount} of {project.scenes.length} scenes have verified clips.</p>
        </div>
      </div>
    );
  }

  return (
    <>
      <StageHeader
        title="Media Selection"
        detail="Choose the perfect stock clip for each scene. Use AI to auto-select based on relevance."
      />
      
      {!hasClips ? (
        <EmptyAction
          label="Search Pexels Library"
          busy={busy === "fetch-clips"}
          onClick={() => run("fetch-clips", () => api.fetchClips(project.id))}
        />
      ) : (
        <div className="mb-6 flex justify-end">
          <Button
            className="glass border-forge-accent/20 text-forge-accent hover:bg-forge-accent/10"
            busy={busy === "auto-select"}
            onClick={() => run("auto-select", () => api.autoSelectClips(project.id))}
          >
            <Sparkles className="h-4 w-4" /> Smart Auto-Select
          </Button>
        </div>
      )}

      <div className="space-y-8">
        {project.scenes.map((scene) => (
          <div key={scene.id} className="space-y-4">
            <div className="flex items-center gap-3 border-l-2 border-forge-red pl-4">
              <span className="text-[10px] font-black uppercase tracking-widest text-zinc-500">Scene {scene.scene_index}</span>
              <h3 className="text-sm font-bold text-white truncate max-w-xl">
                {scene.description}
              </h3>
              <Badge tone="accent" className="ml-auto">{scene.visual_keyword}</Badge>
            </div>
            
            {scene.clips.length === 0 ? (
              <div className="rounded-xl border border-dashed border-forge-border p-8 text-center text-xs text-zinc-600">
                No matching media found for this segment.
              </div>
            ) : (
              <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                {scene.clips.map((clip) => (
                  <motion.button
                    key={clip.id}
                    whileHover={{ y: -4 }}
                    onClick={() =>
                      run(`clip-${clip.id}`, () => api.selectClip(project.id, scene.id, clip.id))
                    }
                    className={`group relative overflow-hidden rounded-xl border bg-forge-panel transition-all duration-300 ${
                      clip.selected
                        ? "border-forge-red ring-4 ring-forge-red/10 shadow-glow-red"
                        : "border-forge-border hover:border-zinc-500"
                    }`}
                  >
                    <div className="aspect-video relative overflow-hidden bg-zinc-900">
                      {clip.image_url ? (
                        <Image
                          src={clip.image_url}
                          alt=""
                          width={400}
                          height={225}
                          className={`h-full w-full object-cover transition-transform duration-500 ${clip.selected ? "scale-105" : "group-hover:scale-105"}`}
                        />
                      ) : (
                        <div className="flex h-full items-center justify-center text-[10px] font-bold uppercase tracking-widest text-zinc-700">
                          No Preview
                        </div>
                      )}
                      {clip.selected && (
                        <div className="absolute inset-0 bg-forge-red/10 flex items-center justify-center">
                          <div className="rounded-full bg-forge-red p-2 shadow-lg">
                            <Check className="h-4 w-4 text-white" />
                          </div>
                        </div>
                      )}
                    </div>
                    <div className="flex items-center justify-between p-3">
                      <div className="space-y-0.5">
                        <div className="text-[10px] font-black text-white">{clip.width}×{clip.height}</div>
                        <div className="text-[9px] font-bold text-zinc-500">{clip.duration}s clip</div>
                      </div>
                      <Badge tone={clip.selected ? "red" : "default"} className="text-[8px]">{clip.selected ? "Active" : "Select"}</Badge>
                    </div>
                  </motion.button>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>

      {hasClips && (
        <ActionRow>
          <Button
            className="w-full sm:w-auto bg-gradient-to-r from-forge-red to-forge-red2 text-white shadow-xl shadow-forge-red/20"
            busy={busy === "approve-clips"}
            onClick={() => run("approve-clips", () => api.approveClips(project.id))}
          >
            <Check className="h-4 w-4" /> Confirm & Download Assets
          </Button>
        </ActionRow>
      )}
    </>
  );
}
