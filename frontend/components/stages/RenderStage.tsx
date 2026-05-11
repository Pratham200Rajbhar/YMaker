import { Wand2, Download, Play, CheckCircle2, AlertCircle, Loader2 } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { api, API_BASE, mediaUrl } from "@/lib/api";
import { Button } from "@/components/ui";
import { StageProps, StageHeader } from "./shared";

export function RenderStage({ project, busy, run, readOnly, providerLabel }: StageProps) {
  const video = mediaUrl(project.render?.render_path);
  const isVideo = !!video;
  const status = project.render?.render_status ?? "idle";
  const isRendering = status === "queued" || status === "rendering";

  return (
    <div className="space-y-8">
      <StageHeader
        title="Final Production"
        detail="The final stage. We'll composite your clips, audio, and subtitles into a finished masterpiece."
        providerLabel={providerLabel}
      />

      <div className="grid gap-6 md:grid-cols-2">
        <div className="space-y-4">
          <div className="rounded-2xl border border-forge-border bg-forge-panel2/20 p-6">
            <h3 className="text-sm font-bold text-zinc-400 uppercase tracking-widest mb-4">Production Status</h3>
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  {status === "complete" ? (
                    <div className="flex h-8 w-8 items-center justify-center rounded-full bg-emerald-500/10 border border-emerald-500/20">
                      <CheckCircle2 className="h-4 w-4 text-emerald-400" />
                    </div>
                  ) : isRendering ? (
                    <div className="flex h-8 w-8 items-center justify-center rounded-full bg-orange-500/10 border border-orange-500/20">
                      <Loader2 className="h-4 w-4 text-orange-400 animate-spin" />
                    </div>
                  ) : (
                    <div className="flex h-8 w-8 items-center justify-center rounded-full bg-white/5 border border-white/10">
                      <Play className="h-4 w-4 text-zinc-500" />
                    </div>
                  )}
                  <div>
                    <span className="block text-sm font-bold text-white capitalize">{status}</span>
                    <span className="text-[10px] font-medium text-zinc-500 uppercase tracking-tight">
                      {isRendering ? "Writing frames to disk..." : status === "complete" ? "Ready for distribution" : "Waiting to start"}
                    </span>
                  </div>
                </div>
              </div>

              {isRendering && (
                <div className="space-y-2 pt-2">
                  <div className="h-1.5 w-full overflow-hidden rounded-full bg-zinc-800">
                    <motion.div 
                      className="h-full bg-gradient-to-r from-forge-red to-orange-500"
                      initial={{ x: "-100%" }}
                      animate={{ x: "0%" }}
                      transition={{ duration: 10, repeat: Infinity, ease: "linear" }}
                    />
                  </div>
                  <p className="text-[10px] text-zinc-500 text-center font-bold uppercase tracking-widest italic">This may take a few minutes depending on length</p>
                </div>
              )}

              {project.render?.error_message && (
                <div className="mt-4 flex items-start gap-3 rounded-xl border border-forge-red/20 bg-forge-red/5 p-3">
                  <AlertCircle className="mt-0.5 h-4 w-4 text-forge-red" />
                  <p className="text-xs font-medium text-forge-red">{project.render.error_message}</p>
                </div>
              )}
            </div>
          </div>

          {!readOnly && (
            <div className="rounded-2xl border border-forge-border bg-forge-panel2/20 p-6">
              <h3 className="text-sm font-bold text-zinc-400 uppercase tracking-widest mb-4">Actions</h3>
              <Button
                className="w-full bg-gradient-to-r from-forge-red to-forge-red2 text-white shadow-xl shadow-forge-red/20 hover:scale-[1.02]"
                busy={busy === "render"}
                disabled={isRendering}
                onClick={() => run("render", () => api.startRender(project.id))}
              >
                <Wand2 className="h-4 w-4" /> 
                {status === "complete" ? "Regenerate Video" : "Start Rendering"}
              </Button>
            </div>
          )}
        </div>

        <div className="relative">
          <AnimatePresence mode="wait">
            {isVideo && video ? (
              <motion.div 
                key="player"
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                className="space-y-6"
              >
                <div className={`relative max-h-[500px] mx-auto overflow-hidden rounded-2xl border border-forge-border bg-black shadow-2xl group ${project.video_format === "shorts" ? "aspect-[9/16]" : "aspect-video"}`}>
                  <video
                    className="h-full w-full object-cover"
                    controls
                    src={video}
                  />
                  <div className="absolute inset-0 pointer-events-none border border-white/5 rounded-2xl" />
                </div>
                <div className="flex justify-center">
                  <a
                    className="inline-flex items-center gap-3 rounded-xl bg-white px-8 py-3 text-sm font-black text-black transition-all hover:scale-105 active:scale-95 shadow-xl hover:shadow-white/10"
                    href={`${API_BASE}${project.render?.render_path}`}
                    download
                  >
                    <Download className="h-5 w-5" /> Download Master
                  </a>
                </div>
              </motion.div>
            ) : (
              <motion.div 
                key="placeholder"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className={`flex max-h-[500px] mx-auto flex-col items-center justify-center rounded-2xl border-2 border-dashed border-forge-border/50 bg-white/[0.02] text-center p-8 ${project.video_format === "shorts" ? "aspect-[9/16]" : "aspect-video"}`}
              >
                <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-zinc-900 border border-zinc-800">
                  <Wand2 className="h-8 w-8 text-zinc-700" />
                </div>
                <h4 className="text-lg font-bold text-zinc-400">Preview Unavailable</h4>
                <p className="mt-2 text-xs text-zinc-600 font-medium leading-relaxed">
                  The video will appear here once the rendering process is complete.
                </p>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
}
