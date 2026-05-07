import { useState, useEffect } from "react";
import { Save, Wand2, Check, RefreshCw } from "lucide-react";
import { api } from "@/lib/api";
import { Button, Field, inputClass } from "@/components/ui";
import type { Script } from "@/lib/types";
import { StageProps, StageHeader, MetaBox, EmptyAction, ActionRow, stripScript } from "./shared";

export function ScriptStage({ project, busy, run, readOnly }: StageProps) {
  const [draft, setDraft] = useState<Script | null>(project.latest_script);
  useEffect(() => setDraft(project.latest_script), [project.latest_script]);

  const canEdit = !readOnly && draft && !draft.approved;

  if (readOnly && draft) {
    return (
      <div className="space-y-6">
        <div className="grid gap-4 md:grid-cols-2">
          <MetaBox label="Tone & Style" value={draft.tone} />
          <MetaBox label="Est. Duration" value={draft.estimated_duration} />
        </div>
        <div>
          <p className="mb-3 text-[10px] font-black uppercase tracking-widest text-zinc-500">Video Script Content</p>
          <div className="rounded-xl border border-forge-border bg-forge-bg/50 p-5 text-sm leading-relaxed text-zinc-300">
            {draft.video_script}
          </div>
        </div>
        <div className="flex justify-end pt-2">
          <Button
            className="h-9 border border-forge-border bg-forge-panel text-zinc-400 hover:text-white"
            busy={busy === "generate-script"}
            onClick={() => run("generate-script", () => api.generateScript(project.id))}
          >
            <RefreshCw className="h-3.5 w-3.5" /> Regenerate Script
          </Button>
        </div>
      </div>
    );
  }

  return (
    <>
      <StageHeader
        title="Script Design"
        detail="Our AI generated this script based on your idea. Refine the flow before approving."
      />
      {!draft ? (
        <EmptyAction
          label="Generate script"
          busy={busy === "generate-script"}
          onClick={() => run("generate-script", () => api.generateScript(project.id))}
        />
      ) : (
        <div className="space-y-6">
          <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
            <div className="space-y-4">
              <Field label="Video Script">
                <textarea
                  disabled={!canEdit}
                  className={`${inputClass} min-h-[400px] leading-relaxed`}
                  value={draft.video_script}
                  onChange={(e) => setDraft({ ...draft, video_script: e.target.value })}
                />
              </Field>
              <Field label="Production Notes">
                <textarea
                  disabled={!canEdit}
                  className={`${inputClass} min-h-24`}
                  value={draft.on_screen_notes}
                  placeholder="Notes for visual overlay or pacing..."
                  onChange={(e) => setDraft({ ...draft, on_screen_notes: e.target.value })}
                />
              </Field>
            </div>
            
            <div className="space-y-6">
              <div className="space-y-4">
                <MetaBox label="Tone" value={draft.tone} />
                <MetaBox label="Duration" value={draft.estimated_duration} />
              </div>
              
              {draft.title_suggestions.length > 0 && (
                <div className="rounded-xl border border-forge-border bg-forge-panel2/50 p-4">
                  <p className="mb-3 text-[10px] font-black uppercase tracking-widest text-zinc-500">Suggested Titles</p>
                  <div className="flex flex-col gap-2">
                    {draft.title_suggestions.map((title) => (
                      <div key={title} className="rounded-lg border border-white/5 bg-white/[0.02] px-3 py-2 text-xs font-medium text-zinc-300">
                        {title}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>

          <ActionRow>
            <Button
              className="border border-forge-border bg-forge-panel text-zinc-200 hover:bg-forge-panel2"
              busy={busy === "save-script"}
              disabled={!canEdit}
              onClick={() =>
                run("save-script", () => api.saveScript(project.id, stripScript(draft)))
              }
            >
              <Save className="h-4 w-4" /> Save Draft
            </Button>
            <Button
              className="border border-forge-border bg-forge-panel text-zinc-200 hover:bg-forge-panel2"
              busy={busy === "generate-script"}
              onClick={() => run("generate-script", () => api.generateScript(project.id))}
            >
              <RefreshCw className="h-4 w-4" /> Regenerate
            </Button>
            <Button
              className="ml-auto bg-gradient-to-r from-forge-red to-forge-red2 text-white shadow-lg shadow-forge-red/20"
              busy={busy === "approve-script"}
              disabled={draft.approved}
              onClick={() => run("approve-script", () => api.approveScript(project.id))}
            >
              <Check className="h-4 w-4" /> {draft.approved ? "Approved" : "Approve & Continue"}
            </Button>
          </ActionRow>
        </div>
      )}
    </>
  );
}
