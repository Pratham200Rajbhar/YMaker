import { useState, useEffect } from "react";
import { Save, Wand2, Check } from "lucide-react";
import { motion } from "framer-motion";
import { api } from "@/lib/api";
import { Button, Field, Badge, inputClass } from "@/components/ui";
import type { Scene } from "@/lib/types";
import { StageProps, StageHeader, EmptyAction, ActionRow, updateSceneDraft } from "./shared";

export function ScenesStage({ project, busy, run, readOnly }: StageProps) {
  const [drafts, setDrafts] = useState<Scene[]>(project.scenes);
  useEffect(() => setDrafts(project.scenes), [project.scenes]);
  const hasScenes = drafts.length > 0;

  if (readOnly && hasScenes) {
    return (
      <div className="space-y-3">
        {drafts.map((scene) => (
          <div key={scene.id} className="flex items-center gap-4 rounded-xl border border-forge-border bg-forge-bg/50 px-4 py-3">
            <div className="flex h-8 w-16 shrink-0 items-center justify-center rounded-lg bg-forge-panel border border-forge-border text-[10px] font-black text-zinc-500 uppercase">
              S-{scene.scene_index}
            </div>
            <span className="truncate text-sm text-zinc-400 font-medium">{scene.description}</span>
            <Badge tone="accent" className="ml-auto shrink-0">{scene.visual_keyword}</Badge>
          </div>
        ))}
      </div>
    );
  }

  return (
    <>
      <StageHeader
        title="Visual Breakdown"
        detail="We've broken your script into logical scenes. Adjust the keywords to influence stock media search."
      />
      {!hasScenes ? (
        <EmptyAction
          label="Analyze script & breakdown scenes"
          busy={busy === "generate-scenes"}
          onClick={() => run("generate-scenes", () => api.generateScenes(project.id))}
        />
      ) : (
        <div className="space-y-4">
          {drafts.map((scene, index) => (
            <motion.div 
              key={scene.id} 
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: index * 0.05 }}
              className="group relative rounded-xl border border-forge-border bg-forge-panel2/30 p-5 transition-all hover:bg-forge-panel2/50"
            >
              <div className="mb-5 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="flex h-7 w-12 items-center justify-center rounded-lg bg-forge-red/10 border border-forge-red/20 text-[10px] font-black text-forge-red uppercase">
                    S-{scene.scene_index}
                  </div>
                  <Badge className="bg-white/5 border-white/10">{scene.duration_seconds}s segment</Badge>
                </div>
                {!readOnly && (
                   <Button
                    className="h-8 px-3 text-[10px] border border-forge-border bg-forge-panel text-zinc-400 hover:text-white"
                    busy={busy === `scene-${scene.id}`}
                    disabled={scene.approved}
                    onClick={() => run(`scene-${scene.id}`, () => api.saveScene(project.id, scene))}
                  >
                    <Save className="h-3 w-3" /> Quick Save
                  </Button>
                )}
              </div>
              
              <div className="grid gap-5 md:grid-cols-[1fr_240px_100px]">
                <Field label="Visual Description">
                  <textarea
                    disabled={readOnly || scene.approved}
                    className={`${inputClass} min-h-24 py-2 text-sm leading-relaxed`}
                    value={scene.description}
                    onChange={(e) => updateSceneDraft(drafts, setDrafts, index, { description: e.target.value })}
                  />
                </Field>
                <Field label="Search Keyword">
                  <div className="relative">
                    <input
                      disabled={readOnly || scene.approved}
                      className={`${inputClass} pr-10`}
                      value={scene.visual_keyword}
                      onChange={(e) => updateSceneDraft(drafts, setDrafts, index, { visual_keyword: e.target.value })}
                    />
                    {!readOnly && !scene.approved && (
                      <button
                        type="button"
                        className="absolute right-2 top-1/2 -translate-y-1/2 flex h-7 w-7 items-center justify-center rounded-md bg-zinc-800 text-zinc-500 transition hover:bg-forge-accent hover:text-white"
                        title="Optimize keyword"
                        onClick={async () => {
                          try {
                            const { optimized_keyword } = await api.optimizeKeyword(scene.description, scene.visual_keyword);
                            updateSceneDraft(drafts, setDrafts, index, { visual_keyword: optimized_keyword });
                          } catch (err) {
                            console.error("Keyword optimization failed", err);
                          }
                        }}
                      >
                        <Wand2 className="h-3.5 w-3.5" />
                      </button>
                    )}
                  </div>
                </Field>
                <Field label="Dur (s)">
                  <input
                    disabled={readOnly || scene.approved}
                    className={`${inputClass} text-center`}
                    type="number"
                    value={scene.duration_seconds}
                    onChange={(e) =>
                      updateSceneDraft(drafts, setDrafts, index, { duration_seconds: Number(e.target.value) })
                    }
                  />
                </Field>
              </div>
              
              <div className="mt-4">
                <Field label="Voiceover Script Fragment">
                  <textarea
                    disabled={readOnly || scene.approved}
                    className={`${inputClass} mt-2 min-h-20 py-2 bg-black/20 text-zinc-400`}
                    value={scene.voiceover_text}
                    onChange={(e) => updateSceneDraft(drafts, setDrafts, index, { voiceover_text: e.target.value })}
                  />
                </Field>
              </div>
            </motion.div>
          ))}

          {!readOnly && (
            <ActionRow>
              <Button
                className="bg-gradient-to-r from-forge-red to-forge-red2 text-white shadow-lg shadow-forge-red/20"
                busy={busy === "approve-scenes"}
                disabled={drafts.every((scene) => scene.approved)}
                onClick={() => run("approve-scenes", () => api.approveScenes(project.id))}
              >
                <Check className="h-4 w-4" /> Finalize Breakdown
              </Button>
            </ActionRow>
          )}
        </div>
      )}
    </>
  );
}
