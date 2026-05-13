import { useState } from "react";
import { Play, Check, RefreshCw, Mic } from "lucide-react";
import { motion } from "framer-motion";
import { api, mediaUrl } from "@/lib/api";
import { Button, Field, Badge, inputClass } from "@/components/ui";
import { StageProps, StageHeader, ActionRow } from "./shared";

const VOICES = [
  "Magpie-Multilingual.HI-IN.Aria",
  "Magpie-Multilingual.HI-IN.John",
  "Magpie-Multilingual.HI-IN.Sofia",
  "Magpie-Multilingual.HI-IN.Jason",
  "Magpie-Multilingual.HI-IN.Leo",
];

export function VoiceStage({ project, busy, run, readOnly, providerLabel }: StageProps) {
  const [voice, setVoice] = useState(project.render?.voice_name ?? VOICES[0]);
  const audio = mediaUrl(project.render?.voiceover_path);
  const isImageStory = project.video_format === "image_story";

  if (readOnly) {
    return (
      <div className="space-y-4">
        <StageHeader
          title="Audio Forge"
          detail="Generate your project voiceover using NVIDIA Magpie TTS multilingual models."
          providerLabel={providerLabel}
        />
        <div className="flex items-center gap-3">
          <Badge tone="accent" className="px-4">{project.render?.voice_name}</Badge>
          <span className="text-xs font-bold text-zinc-600 uppercase tracking-widest">Audio Master</span>
        </div>
        {audio ? (
          <audio className="w-full" controls src={audio} />
        ) : (
          <p className="text-sm text-zinc-600 italic">No audio master generated.</p>
        )}
        <div className="flex justify-end pt-2">
          <Button
            className="h-9 border border-forge-border bg-forge-panel text-zinc-400 hover:text-white"
            busy={busy === "voice"}
            onClick={() => {
              if (isImageStory) {
                const sceneVoices = Object.fromEntries(
                  project.scenes
                    .filter((s) => s.character_voice)
                    .map((s) => [s.scene_index, s.character_voice])
                );
                run("voice", () => api.generateMultiVoice(project.id, { default_voice: voice, scene_voices: sceneVoices }));
              } else {
                run("voice", () => api.generateVoiceover(project.id, voice));
              }
            }}
          >
            <RefreshCw className="h-3.5 w-3.5" /> Regenerate Audio
          </Button>
        </div>
      </div>
    );
  }

  return (
    <>
      <StageHeader
        title="Audio Forge"
        detail="Generate your project voiceover using NVIDIA Magpie TTS multilingual models."
        providerLabel={providerLabel}
      />
      <div className="grid gap-6 md:grid-cols-[1fr_200px]">
        <Field label={isImageStory ? "Default Voice" : "AI Voice Model"}>
          <select
            className={`${inputClass} appearance-none cursor-pointer`}
            value={voice}
            onChange={(e) => setVoice(e.target.value)}
          >
            {VOICES.map((item) => (
              <option key={item} value={item}>{item}</option>
            ))}
          </select>
        </Field>
        <div className="flex items-end">
          <Button
            className="w-full bg-forge-panel border border-forge-border text-white hover:bg-forge-panel2"
            busy={busy === "voice"}
            onClick={() => {
              if (isImageStory) {
                const sceneVoices = Object.fromEntries(
                  project.scenes
                    .filter((s) => s.character_voice)
                    .map((s) => [s.scene_index, s.character_voice])
                );
                run("voice", () => api.generateMultiVoice(project.id, { default_voice: voice, scene_voices: sceneVoices }));
              } else {
                run("voice", () => api.generateVoiceover(project.id, voice));
              }
            }}
          >
            {audio ? (
              <>
                <RefreshCw className="h-4 w-4" /> Regenerate Audio
              </>
            ) : (
              <>
                <Play className="h-4 w-4 fill-current" /> Generate Audio
              </>
            )}
          </Button>
        </div>
      </div>

      {/* Multi-voice assignments for image_story */}
      {isImageStory && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="mt-6 rounded-2xl border border-forge-border bg-forge-panel/40 p-5"
        >
          <div className="flex items-center gap-2 mb-4">
            <Mic className="h-4 w-4 text-forge-red" />
            <h3 className="text-sm font-bold text-white">Per-Scene Voice Assignments</h3>
          </div>
          <div className="space-y-2 max-h-[240px] overflow-y-auto pr-1">
            {project.scenes.map((scene) => (
              <div key={scene.id} className="flex items-center justify-between rounded-lg bg-forge-bg/50 px-3 py-2">
                <div className="flex items-center gap-2">
                  <Badge tone="accent" className="text-[9px]">Scene {scene.scene_index + 1}</Badge>
                  <span className="text-xs text-zinc-400 truncate max-w-[200px]">{scene.description}</span>
                </div>
                <div className="flex items-center gap-2">
                  {scene.character_voice ? (
                    <Badge tone="green" className="text-[9px]">{scene.character_voice}</Badge>
                  ) : (
                    <span className="text-[10px] text-zinc-600 italic">Using default voice</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </motion.div>
      )}

      {audio ? (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="mt-8 rounded-2xl bg-black/40 p-6 border border-white/5"
        >
          <p className="mb-4 text-[10px] font-black uppercase tracking-widest text-zinc-500">Audio Master Preview</p>
          <audio className="w-full" controls src={audio} />
        </motion.div>
      ) : (
        <div className="mt-8 rounded-xl border border-dashed border-forge-border p-12 text-center">
          <p className="text-sm text-zinc-600">Select a voice and click preview to generate the master track.</p>
        </div>
      )}

      <ActionRow>
        <Button
          className="bg-gradient-to-r from-forge-red to-forge-red2 text-white shadow-lg shadow-forge-red/20"
          busy={busy === "approve-voice"}
          disabled={!audio || !!project.render?.voiceover_approved}
          onClick={() => run("approve-voice", () => api.approveVoiceover(project.id))}
        >
          <Check className="h-4 w-4" /> {project.render?.voiceover_approved ? "Approved" : "Approve Voiceover"}
        </Button>
      </ActionRow>
    </>
  );
}
