"use client";

import { useState, useEffect, useCallback } from "react";
import { Wand2, Check, Upload, Trash2, Edit3, Save, ChevronDown, ChevronUp, ImageIcon } from "lucide-react";
import { motion } from "framer-motion";
import { api, API_BASE } from "@/lib/api";
import type { Project, Scene } from "@/lib/types";
import { Button, Badge, inputClass } from "@/components/ui";
import { StageHeader, ActionRow } from "./shared";

const VOICES = [
  "Magpie-Multilingual.HI-IN.Aria",
  "Magpie-Multilingual.HI-IN.John",
  "Magpie-Multilingual.HI-IN.Sofia",
  "Magpie-Multilingual.HI-IN.Jason",
  "Magpie-Multilingual.HI-IN.Leo",
];

interface ImageScenesStageProps {
  project: Project;
  onProjectUpdate: (_p: Project) => void;
}

export function ImageScenesStage({ project, onProjectUpdate }: ImageScenesStageProps) {
  const [generatingPrompts, setGeneratingPrompts] = useState(false);
  const [uploadingSceneId, setUploadingSceneId] = useState<number | null>(null);
  const [editingPromptSceneId, setEditingPromptSceneId] = useState<number | null>(null);
  const [editedPromptText, setEditedPromptText] = useState<Record<number, string>>({});
  const [voiceAssignments, setVoiceAssignments] = useState<Record<number, string>>({});
  const [progress, setProgress] = useState<{ total: number; ready: number; all_ready: boolean }>({ total: 0, ready: 0, all_ready: false });
  const [expandedVoices, setExpandedVoices] = useState<Record<number, boolean>>({});
  const [dragOverSceneId, setDragOverSceneId] = useState<number | null>(null);
  const [urlInputSceneId, setUrlInputSceneId] = useState<number | null>(null);
  const [pastedUrl, setPastedUrl] = useState("");

  const fetchProgress = useCallback(async () => {
    try {
      const data = await api.getImageProgress(project.id);
      setProgress({ total: data.total_scenes, ready: data.images_ready, all_ready: data.all_ready });
    } catch {
      // ignore
    }
  }, [project.id]);

  /* eslint-disable react-hooks/set-state-in-effect */
  useEffect(() => {
    fetchProgress();
  }, [fetchProgress]);

  useEffect(() => {
    const init: Record<number, string> = {};
    project.scenes.forEach((s) => {
      if (s.character_voice) init[s.id] = s.character_voice;
    });
    setVoiceAssignments(init);
  }, [project.scenes]);
  /* eslint-enable react-hooks/set-state-in-effect */

  const hasAnyPrompt = project.scenes.some((s) => !!s.image_prompt);

  async function handleGeneratePrompts() {
    setGeneratingPrompts(true);
    try {
      const updated = await api.generateImagePrompts(project.id);
      onProjectUpdate(updated);
    } catch (err) {
      console.error(err);
    } finally {
      setGeneratingPrompts(false);
    }
  }

  async function handleSavePrompt(scene: Scene) {
    const text = editedPromptText[scene.id];
    if (!text) return;
    try {
      await api.updateImagePrompt(project.id, scene.id, { image_prompt: text, image_prompt_approved: true });
      const updated = await api.getProject(project.id);
      onProjectUpdate(updated);
      setEditingPromptSceneId(null);
    } catch (err) {
      console.error(err);
    }
  }

  async function handleUpload(scene: Scene, file: File) {
    setUploadingSceneId(scene.id);
    try {
      await api.uploadSceneImage(project.id, scene.id, file);
      const updated = await api.getProject(project.id);
      onProjectUpdate(updated);
      await fetchProgress();
    } catch (err) {
      console.error(err);
    } finally {
      setUploadingSceneId(null);
    }
  }

  async function handleUploadByUrl(scene: Scene, url: string) {
    setUploadingSceneId(scene.id);
    try {
      await api.uploadSceneImageByUrl(project.id, scene.id, url);
      const updated = await api.getProject(project.id);
      onProjectUpdate(updated);
      await fetchProgress();
    } catch (err) {
      console.error(err);
    } finally {
      setUploadingSceneId(null);
    }
  }

  async function handleUrlSubmit(scene: Scene) {
    if (!pastedUrl.trim()) return;
    await handleUploadByUrl(scene, pastedUrl.trim());
    setPastedUrl("");
    setUrlInputSceneId(null);
  }

  async function handleDeleteImage(scene: Scene) {
    try {
      await api.deleteSceneImage(project.id, scene.id);
      const updated = await api.getProject(project.id);
      onProjectUpdate(updated);
      await fetchProgress();
    } catch (err) {
      console.error(err);
    }
  }

  async function handleAssignVoice(scene: Scene, voice: string) {
    try {
      await api.assignSceneVoice(project.id, scene.id, { character_voice: voice });
      setVoiceAssignments((prev) => ({ ...prev, [scene.id]: voice }));
    } catch (err) {
      console.error(err);
    }
  }

  function imagePreviewUrl(scene: Scene): string | null {
    if (!scene.image_ready || !scene.uploaded_image_path) return null;
    // Try to construct from known pattern since backend stores full path
    const match = scene.uploaded_image_path.match(/scene_(\d+)\.(\w+)$/);
    if (match) {
      const ext = match[2];
      return `${API_BASE}/storage/project_${project.id}/images/scene_${scene.scene_index}.${ext}`;
    }
    return `${API_BASE}${scene.uploaded_image_path}`;
  }

  return (
    <div className="space-y-6">
      <StageHeader
        title="Image Prompts & Upload"
        detail="Generate AI image prompts for each scene, then upload your generated images."
      />

      {/* Generate Prompts Button */}
      {!hasAnyPrompt && (
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
          <Button
            className="w-full bg-gradient-to-r from-forge-red to-forge-red2 text-white shadow-xl shadow-forge-red/20 hover:scale-[1.02]"
            busy={generatingPrompts}
            onClick={handleGeneratePrompts}
          >
            <Wand2 className="h-4 w-4" /> Generate AI Image Prompts for All Scenes
          </Button>
        </motion.div>
      )}

      {/* Progress Bar */}
      {hasAnyPrompt && (
        <div className="rounded-xl border border-forge-border bg-forge-panel/40 p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-bold uppercase tracking-widest text-zinc-500">Upload Progress</span>
            <span className="text-xs font-bold text-zinc-300">{progress.ready} / {progress.total} images</span>
          </div>
          <div className="h-2 w-full overflow-hidden rounded-full bg-zinc-800">
            <motion.div
              className="h-full bg-gradient-to-r from-forge-red to-forge-red2"
              initial={{ width: 0 }}
              animate={{ width: `${progress.total > 0 ? (progress.ready / progress.total) * 100 : 0}%` }}
              transition={{ duration: 0.5 }}
            />
          </div>
        </div>
      )}

      {/* Scene Cards */}
      <div className="space-y-4">
        {project.scenes.map((scene) => (
          <motion.div
            key={scene.id}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className={`relative rounded-xl border transition-all duration-300 p-5 ${
              dragOverSceneId === scene.id 
                ? "border-forge-red bg-forge-red/10 ring-2 ring-forge-red/20 shadow-glow-red/10 scale-[1.01] z-20" 
                : "border-forge-border bg-forge-panel/40"
            }`}
            onDragOver={(e) => {
              if (!scene.image_ready) {
                e.preventDefault();
                setDragOverSceneId(scene.id);
              }
            }}
            onDragLeave={() => setDragOverSceneId(null)}
            tabIndex={0}
            onPaste={(e) => {
              if (!scene.image_ready) {
                const item = Array.from(e.clipboardData.items).find((x) => x.type.startsWith("image/"));
                if (item) {
                  const file = item.getAsFile();
                  if (file) handleUpload(scene, file);
                }
              }
            }}
            onDrop={(e) => {
              if (!scene.image_ready) {
                e.preventDefault();
                setDragOverSceneId(null);
                
                // 1. Try to get actual file data from items (best for cross-tab drags)
                const items = Array.from(e.dataTransfer.items);
                const imageItem = items.find(item => item.kind === 'file' && item.type.startsWith('image/'));
                if (imageItem) {
                  const file = imageItem.getAsFile();
                  if (file) {
                    handleUpload(scene, file);
                    return;
                  }
                }

                // 2. Check for traditional files (local drag)
                if (e.dataTransfer.files.length > 0) {
                  handleUpload(scene, e.dataTransfer.files[0]);
                  return;
                }

                // 3. Check for URL (web drag)
                const url = e.dataTransfer.getData("text/uri-list") || e.dataTransfer.getData("URL") || e.dataTransfer.getData("text/plain");
                if (url && (url.startsWith("http") || url.startsWith("data:"))) {
                  const firstUrl = url.split("\n")[0].trim();
                  if (firstUrl) {
                    handleUploadByUrl(scene, firstUrl);
                    return;
                  }
                }

                // 4. Fallback to HTML (extract src from <img> tag)
                const html = e.dataTransfer.getData("text/html");
                if (html) {
                  const match = html.match(/src="([^"]+)"/);
                  if (match?.[1]) {
                    handleUploadByUrl(scene, match[1]);
                    return;
                  }
                }
              }
            }}
          >
            {dragOverSceneId === scene.id && (
              <div className="absolute inset-0 z-30 flex flex-col items-center justify-center rounded-xl bg-forge-red/5 backdrop-blur-[2px] pointer-events-none">
                <div className="flex h-16 w-16 items-center justify-center rounded-full bg-forge-red shadow-glow-red">
                  <Upload className="h-8 w-8 text-white" />
                </div>
                <span className="mt-4 text-sm font-black uppercase tracking-widest text-forge-red">Drop Image Here</span>
              </div>
            )}

            <div className="flex items-start justify-between gap-4">
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-1">
                  <Badge tone="accent" className="text-[10px]">Scene {scene.scene_index + 1}</Badge>
                  {scene.image_prompt_approved && (
                    <Badge tone="green" className="text-[10px]"><Check className="h-3 w-3 mr-1" /> Approved</Badge>
                  )}
                </div>
                <p className="text-sm text-zinc-300 leading-relaxed line-clamp-2">{scene.description}</p>
              </div>
            </div>

            {/* Image Prompt Block */}
            {scene.image_prompt && (
              <div className="mt-4 rounded-lg border border-forge-border bg-forge-bg/50 p-3">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-[10px] font-bold uppercase tracking-widest text-zinc-500">Image Prompt</span>
                  {editingPromptSceneId === scene.id ? (
                    <Button className="h-7 px-3 text-xs" onClick={() => handleSavePrompt(scene)}>
                      <Save className="h-3 w-3 mr-1" /> Save
                    </Button>
                  ) : (
                    <button
                      className="flex items-center gap-1 text-xs text-zinc-400 hover:text-white transition-colors"
                      onClick={() => {
                        setEditingPromptSceneId(scene.id);
                        setEditedPromptText((prev) => ({ ...prev, [scene.id]: scene.image_prompt || "" }));
                      }}
                    >
                      <Edit3 className="h-3 w-3" /> Edit Prompt
                    </button>
                  )}
                </div>
                {editingPromptSceneId === scene.id ? (
                  <textarea
                    className={`${inputClass} min-h-[100px] text-xs`}
                    value={editedPromptText[scene.id] || ""}
                    onChange={(e) => setEditedPromptText((prev) => ({ ...prev, [scene.id]: e.target.value }))}
                  />
                ) : (
                  <p className="text-xs text-zinc-400 leading-relaxed">{scene.image_prompt}</p>
                )}
              </div>
            )}

            {/* Image Upload Block */}
            <div className="mt-4">
              {!scene.image_ready ? (
                <div
                  className="relative rounded-xl border-2 border-dashed border-forge-border bg-forge-bg/30 p-8 text-center transition-colors hover:border-forge-red/50"
                >
                  {uploadingSceneId === scene.id ? (
                    <div className="flex items-center justify-center gap-2 text-zinc-400">
                      <div className="h-4 w-4 animate-spin rounded-full border-2 border-forge-red border-t-transparent" />
                      <span className="text-xs font-bold">Uploading...</span>
                    </div>
                  ) : urlInputSceneId === scene.id ? (
                    <div className="flex flex-col items-center gap-2" onClick={(e) => e.stopPropagation()}>
                       <div className="flex w-full items-center gap-2 rounded-lg border border-forge-red/50 bg-zinc-900/50 p-1">
                          <input
                            type="text"
                            placeholder="Paste image URL here..."
                            className="flex-1 bg-transparent px-3 py-2 text-xs text-white outline-none"
                            autoFocus
                            value={pastedUrl}
                            onChange={(e) => setPastedUrl(e.target.value)}
                            onKeyDown={(e) => {
                              if (e.key === "Enter") handleUrlSubmit(scene);
                              if (e.key === "Escape") setUrlInputSceneId(null);
                            }}
                          />
                          <Button
                            size="sm"
                            className="h-7 bg-forge-red text-white text-[10px] px-2"
                            busy={uploadingSceneId === scene.id}
                            onClick={() => handleUrlSubmit(scene)}
                          >
                            Upload
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            className="h-7 text-zinc-400 hover:text-white text-[10px] px-2"
                            onClick={() => setUrlInputSceneId(null)}
                          >
                            Cancel
                          </Button>
                       </div>
                    </div>
                  ) : (
                    <>
                      <Upload className="h-6 w-6 text-zinc-600 mx-auto mb-2" />
                      <p className="text-xs text-zinc-500 font-medium mb-2 relative z-10">
                        Drop image anywhere on card, or{" "}
                        <span 
                          className="text-forge-red hover:underline cursor-pointer" 
                          onClick={(e) => {
                            e.stopPropagation();
                            document.getElementById(`file-input-${scene.id}`)?.click();
                          }}
                        >
                          browse
                        </span>
                        {" "}or{" "}
                        <span 
                          className="text-forge-red hover:underline cursor-pointer" 
                          onClick={(e) => {
                            e.stopPropagation();
                            setUrlInputSceneId(scene.id);
                          }}
                        >
                          paste URL
                        </span>
                        {" "}or <span className="text-zinc-400">Ctrl+V</span>
                      </p>
                      <input
                        id={`file-input-${scene.id}`}
                        type="file"
                        accept="image/jpeg,image/png,image/webp"
                        className="absolute inset-0 opacity-0 cursor-pointer"
                        onChange={(e) => {
                          const file = e.target.files?.[0];
                          if (file) handleUpload(scene, file);
                          e.target.value = "";
                        }}
                      />
                    </>
                  )}
                </div>
              ) : (
                <div className="rounded-xl border border-forge-border bg-forge-bg/30 p-3">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <Check className="h-4 w-4 text-emerald-400" />
                      <span className="text-xs font-bold text-emerald-400">Image Ready</span>
                    </div>
                    <button
                      className="flex items-center gap-1 text-xs text-zinc-500 hover:text-forge-red transition-colors"
                      onClick={() => handleDeleteImage(scene)}
                    >
                      <Trash2 className="h-3 w-3" /> Remove & Re-upload
                    </button>
                  </div>
                  <div className="relative rounded-lg overflow-hidden bg-black/40 aspect-video">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                      src={imagePreviewUrl(scene) || ""}
                      alt={`Scene ${scene.scene_index}`}
                      className="w-full h-full object-contain"
                      onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
                    />
                  </div>
                </div>
              )}
            </div>

            {/* Voice Assignment Block */}
            <div className="mt-4">
              <button
                className="flex items-center gap-2 text-xs font-bold text-zinc-500 hover:text-zinc-300 transition-colors"
                onClick={() => setExpandedVoices((prev) => ({ ...prev, [scene.id]: !prev[scene.id] }))}
              >
                {expandedVoices[scene.id] ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
                Character Voice for This Scene (optional)
              </button>
              {expandedVoices[scene.id] && (
                <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} className="mt-2">
                  <select
                    className={`${inputClass} text-xs`}
                    value={voiceAssignments[scene.id] || ""}
                    onChange={(e) => handleAssignVoice(scene, e.target.value)}
                  >
                    <option value="">Using default voice</option>
                    {VOICES.map((v) => (
                      <option key={v} value={v}>{v}</option>
                    ))}
                  </select>
                  {voiceAssignments[scene.id] && (
                    <Badge tone="accent" className="mt-2 text-[10px]">{voiceAssignments[scene.id]}</Badge>
                  )}
                </motion.div>
              )}
            </div>
          </motion.div>
        ))}
      </div>

      {/* Proceed to Voiceover */}
      {progress.all_ready && (
        <ActionRow>
          <Button
            className="bg-gradient-to-r from-forge-red to-forge-red2 text-white shadow-lg shadow-forge-red/20"
            busy={generatingPrompts}
            onClick={async () => {
              setGeneratingPrompts(true);
              try {
                const updated = await api.approveImages(project.id);
                onProjectUpdate(updated);
              } catch (err) {
                console.error(err);
              } finally {
                setGeneratingPrompts(false);
              }
            }}
          >
            <ImageIcon className="h-4 w-4 mr-2" /> Proceed to Voiceover
          </Button>
        </ActionRow>
      )}
    </div>
  );
}
