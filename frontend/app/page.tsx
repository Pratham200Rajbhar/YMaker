"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ArrowRight, Clapperboard, Plus, Trash2, Wand2, Sparkles, Settings as SettingsIcon } from "lucide-react";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";

import { api } from "@/lib/api";
import type { ProjectListItem, VideoFormat, VideoLength, Settings } from "@/lib/types";
import { Badge, Button, Panel, inputClass } from "@/components/ui";


export default function HomePage() {
  const router = useRouter();
  const [idea, setIdea] = useState("");
  const [category, setCategory] = useState("General");
  const [categories, setCategories] = useState<string[]>([]);
  const [format, setFormat] = useState<VideoFormat>("shorts");
  const [videoLength, setVideoLength] = useState<VideoLength>("auto");
  const [language, setLanguage] = useState("english");
  const [subtitlesEnabled, setSubtitlesEnabled] = useState(true);
  const [subtitleLanguage, setSubtitleLanguage] = useState("english");
  const [projects, setProjects] = useState<ProjectListItem[]>([]);
  const [activeCategoryFilter, setActiveCategoryFilter] = useState("All");
  const [settings, setSettings] = useState<Settings | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    api.listProjects().then(setProjects).catch((err) => setError(err.message));
    api.listCategories().then(setCategories).catch((err) => console.error("Categories fetch failed", err));
    api.getSettings().then(setSettings).catch((err) => console.error("Settings fetch failed", err));
  }, []);

  async function createProject() {
    setBusy(true);
    setError("");
    try {
      const project = await api.createProject(idea, category, format, videoLength, language, subtitlesEnabled, subtitleLanguage);
      router.push(`/projects/${project.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create project");
    } finally {
      setBusy(false);
    }
  }

  async function deleteProject(id: number) {
    if (!confirm("Are you sure you want to delete this project?")) return;
    try {
      await api.deleteProject(id);
      setProjects((prev) => prev.filter((p) => p.id !== id));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed");
    }
  }

  async function optimizeIdea() {
    if (idea.trim().length < 5) return;
    setBusy(true);
    setError("");
    try {
      const { optimized_idea } = await api.optimizeIdea(idea);
      setIdea(optimized_idea);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Optimization failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="min-h-screen bg-forge-bg selection:bg-forge-red/30 selection:text-forge-red">
      {/* Background Glow */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute -top-[10%] -left-[10%] w-[40%] h-[40%] bg-forge-red/5 rounded-full blur-[120px]" />
        <div className="absolute top-[20%] -right-[5%] w-[30%] h-[30%] bg-forge-accent/5 rounded-full blur-[100px]" />
      </div>

      <div className="relative mx-auto max-w-6xl px-6 py-12 md:py-20">
        <header className="mb-12 flex items-center justify-between">
          <motion.div 
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            className="flex items-center gap-4"
          >
            <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-gradient-to-br from-forge-red to-forge-red2 text-white shadow-lg shadow-forge-red/20">
              <Clapperboard className="h-6 w-6" />
            </div>
            <div>
              <h1 className="text-3xl font-black tracking-tight text-white">MakeVideo</h1>
              <p className="text-sm font-medium text-zinc-500">Human-reviewed AI video production</p>
            </div>
          </motion.div>
          <motion.div
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            className="flex items-center gap-4"
          >
            <Link 
              href="/settings"
              className="flex h-10 w-10 items-center justify-center rounded-xl bg-white/5 text-zinc-400 border border-white/10 transition-all hover:bg-white/10 hover:text-white"
              title="System Settings"
            >
              <SettingsIcon className="h-5 w-5" />
            </Link>
            <Badge tone={settings?.llm_provider === "ollama" ? "red" : "accent"} className="px-4 py-1.5 border-white/10 bg-white/5">
              {settings?.llm_provider === "ollama" ? "Local-first Engine" : 
               settings?.llm_provider === "openai" ? "OpenAI Powered" :
               settings?.llm_provider === "openrouter" ? "OpenRouter Engine" :
               settings?.llm_provider === "vertex" ? "Gemini Pro AI" : "AI Engine"}
            </Badge>
          </motion.div>
        </header>

        <section className="grid gap-8 lg:grid-cols-[1.1fr_0.9fr]">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
          >
            <Panel className="relative overflow-hidden">
              <div className="mb-8">
                <h2 className="text-3xl font-black tracking-tight text-white md:text-4xl">Forge a video from a rough idea</h2>
                <p className="mt-3 max-w-2xl text-base leading-relaxed text-zinc-400">
                  MakeVideo automates script, scenes, and rendering while keeping you in the director&apos;s chair.
                </p>
              </div>
              
              <div className="group relative mb-8">
                <div className="absolute -inset-0.5 rounded-2xl bg-gradient-to-r from-forge-red/20 to-forge-accent/20 opacity-0 blur transition duration-500 group-focus-within:opacity-100 group-hover:opacity-75" />
                <div className="relative">
                  <textarea
                    className={`${inputClass} min-h-44 resize-y pr-14 transition-all duration-300 bg-black/40 backdrop-blur-xl border-white/5 group-hover:border-white/10`}
                    placeholder="Describe your video idea in detail..."
                    value={idea}
                    onChange={(event) => setIdea(event.target.value)}
                  />
                  <div className="absolute right-3 top-3 flex flex-col gap-2">
                    <button
                      type="button"
                      className="flex h-10 w-10 items-center justify-center rounded-xl bg-white/5 text-zinc-400 backdrop-blur-md border border-white/10 transition-all hover:bg-forge-red hover:text-white hover:scale-110 disabled:opacity-50"
                      title="Optimize idea with AI"
                      disabled={busy || idea.trim().length < 5}
                      onClick={optimizeIdea}
                    >
                      <Wand2 className="h-4 w-4" />
                    </button>
                  </div>
                </div>
              </div>

              <div className="mt-8 flex flex-wrap items-end gap-6">
                <div className="space-y-2">
                  <span className="text-[10px] font-bold uppercase tracking-widest text-zinc-500 ml-1">Category</span>
                  <div className="relative">
                    <select
                      className={`${inputClass} !py-2.5 !px-4 !h-[46px] min-w-[160px] bg-white/[0.03] border-white/5 backdrop-blur-md font-bold text-sm`}
                      value={category}
                      onChange={(e) => setCategory(e.target.value)}
                    >
                      {categories.map((cat) => (
                        <option key={cat} value={cat} className="bg-zinc-900">
                          {cat}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>

                <div className="space-y-2">
                  <span className="text-[10px] font-bold uppercase tracking-widest text-zinc-500 ml-1">Format</span>
                  <div className="flex rounded-xl bg-white/[0.03] p-1.5 border border-white/5 backdrop-blur-md">
                    {[
                      { id: "shorts", label: "Shorts", icon: "📱" },
                      { id: "long", label: "Long Form", icon: "🎬" }
                    ].map((v) => (
                      <button
                        key={v.id}
                        className={`flex items-center gap-2 rounded-lg px-6 py-2.5 text-sm font-bold transition-all duration-300 ${format === v.id ? "bg-forge-red text-white shadow-lg shadow-forge-red/30 scale-105" : "text-zinc-500 hover:text-zinc-300 hover:bg-white/5"}`}
                        onClick={() => setFormat(v.id as VideoFormat)}
                      >
                        <span className="text-xs">{v.icon}</span>
                        {v.label}
                      </button>
                    ))}
                  </div>
                </div>

                <AnimatePresence mode="wait">
                  {format === "long" && (
                    <motion.div 
                      initial={{ opacity: 0, x: -10 }}
                      animate={{ opacity: 1, x: 0 }}
                      exit={{ opacity: 0, x: -10 }}
                      className="space-y-2"
                    >
                      <span className="text-[10px] font-bold uppercase tracking-widest text-zinc-500 ml-1">Video Length</span>
                      <div className="flex rounded-xl bg-white/[0.03] p-1.5 border border-white/5 backdrop-blur-md">
                        {[
                          { id: "auto", label: "Auto", desc: "AI Decides" },
                          { id: "short", label: "Short", desc: "~2m" },
                          { id: "medium", label: "Medium", desc: "~5m" },
                          { id: "long", label: "Long", desc: "10m+" }
                        ].map((v) => (
                          <button
                            key={v.id}
                            className={`flex flex-col items-center rounded-lg px-4 py-2 text-sm font-bold transition-all duration-300 ${videoLength === v.id ? "bg-forge-accent text-white shadow-lg shadow-forge-accent/30 scale-105" : "text-zinc-500 hover:text-zinc-300 hover:bg-white/5"}`}
                            onClick={() => setVideoLength(v.id as VideoLength)}
                            title={v.desc}
                          >
                            {v.label}
                            <span className="text-[8px] opacity-60 font-black uppercase tracking-tighter">{v.id === "auto" ? "✨" : v.desc}</span>
                          </button>
                        ))}
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>

                <div className="space-y-2">
                  <span className="text-[10px] font-bold uppercase tracking-widest text-zinc-500 ml-1">Language</span>
                  <div className="flex rounded-xl bg-white/[0.03] p-1.5 border border-white/5 backdrop-blur-md">
                    {["english", "hindi"].map((v) => (
                      <button
                        key={v}
                        className={`rounded-lg px-6 py-2.5 text-sm font-bold transition-all duration-300 ${language === v ? "bg-forge-red text-white shadow-lg shadow-forge-red/30 scale-105" : "text-zinc-500 hover:text-zinc-300 hover:bg-white/5"}`}
                        onClick={() => setLanguage(v)}
                      >
                        {v.charAt(0).toUpperCase() + v.slice(1)}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="space-y-2">
                  <span className="text-[10px] font-bold uppercase tracking-widest text-zinc-500 ml-1">Subtitles</span>
                  <div className="flex rounded-xl bg-white/[0.03] p-1.5 border border-white/5 backdrop-blur-md">
                    <button
                      className={`rounded-lg px-6 py-2.5 text-sm font-bold transition-all duration-300 ${subtitlesEnabled ? "bg-forge-red text-white shadow-lg shadow-forge-red/30 scale-105" : "text-zinc-500 hover:text-zinc-300 hover:bg-white/5"}`}
                      onClick={() => setSubtitlesEnabled(true)}
                    >
                      On
                    </button>
                    <button
                      className={`rounded-lg px-6 py-2.5 text-sm font-bold transition-all duration-300 ${!subtitlesEnabled ? "bg-forge-red text-white shadow-lg shadow-forge-red/30 scale-105" : "text-zinc-500 hover:text-zinc-300 hover:bg-white/5"}`}
                      onClick={() => setSubtitlesEnabled(false)}
                    >
                      Off
                    </button>
                  </div>
                </div>

                {subtitlesEnabled && (
                  <motion.div 
                    initial={{ opacity: 0, scale: 0.95 }}
                    animate={{ opacity: 1, scale: 1 }}
                    className="space-y-2"
                  >
                    <span className="text-[10px] font-bold uppercase tracking-widest text-zinc-500 ml-1">Subtitle Language</span>
                    <div className="flex rounded-xl bg-white/[0.03] p-1.5 border border-white/5 backdrop-blur-md">
                      {["english", "hindi"].map((v) => (
                        <button
                          key={v}
                          className={`rounded-lg px-6 py-2.5 text-sm font-bold transition-all duration-300 ${subtitleLanguage === v ? "bg-forge-accent text-white shadow-lg shadow-forge-accent/30 scale-105" : "text-zinc-500 hover:text-zinc-300 hover:bg-white/5"}`}
                          onClick={() => setSubtitleLanguage(v)}
                        >
                          {v.charAt(0).toUpperCase() + v.slice(1)}
                        </button>
                      ))}
                    </div>
                  </motion.div>
                )}


                <div className="ml-auto">
                  <Button 
                    className="w-full sm:w-auto bg-gradient-to-r from-forge-red to-forge-red2 text-white shadow-xl shadow-forge-red/20 hover:scale-[1.02]" 
                    busy={busy} 
                    disabled={idea.trim().length < 5} 
                    onClick={createProject}
                  >
                    <Plus className="h-4 w-4" />
                    Create Project
                  </Button>
                </div>
              </div>
              {error ? <p className="mt-4 text-sm font-medium text-forge-red animate-in">{error}</p> : null}
            </Panel>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
          >
            <Panel className="flex flex-col h-full">
              <div className="mb-6 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Sparkles className="h-4 w-4 text-forge-red" />
                  <h2 className="text-xl font-bold text-white">Recent Projects</h2>
                </div>
                <Badge tone="accent">{projects.length} Total</Badge>
              </div>

              {projects.length > 0 && (
                <div className="mb-6 flex flex-wrap gap-2 overflow-x-auto pb-2 scrollbar-hide">
                  {["All", ...Array.from(new Set(projects.map(p => p.category)))].map(cat => (
                    <button
                      key={cat}
                      onClick={() => setActiveCategoryFilter(cat)}
                      className={`px-3 py-1 rounded-full text-xs font-bold transition-all ${activeCategoryFilter === cat ? "bg-forge-red text-white" : "bg-white/5 text-zinc-500 hover:bg-white/10"}`}
                    >
                      {cat}
                    </button>
                  ))}
                </div>
              )}
              
              <div className="flex-1 space-y-4 overflow-y-auto pr-1 max-h-[500px] scrollbar-hide">
                <AnimatePresence mode="popLayout">
                  {projects.length === 0 ? (
                    <motion.div 
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      className="flex flex-col items-center justify-center rounded-xl border border-dashed border-forge-border/50 bg-white/[0.02] py-20 text-center"
                    >
                      <Clapperboard className="h-10 w-10 text-zinc-700 mb-3" />
                      <p className="text-sm font-medium text-zinc-500">No projects found. Create your first video above.</p>
                    </motion.div>
                  ) : (
                    projects
                      .filter(p => activeCategoryFilter === "All" || p.category === activeCategoryFilter)
                      .map((project, idx) => (
                      <motion.div 
                        key={project.id} 
                        layout
                        initial={{ opacity: 0, x: -10 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: idx * 0.05 }}
                        className="group relative"
                      >
                        <Link 
                          href={`/projects/${project.id}`} 
                          className="block rounded-xl border border-forge-border bg-forge-panel2/30 p-5 transition-all duration-300 hover:border-forge-red/40 hover:bg-forge-panel2/60 pr-14"
                        >
                          <div className="flex items-start justify-between">
                            <div className="space-y-3">
                              <h3 className="line-clamp-1 text-lg font-bold text-white group-hover:text-forge-red transition-colors">{project.title}</h3>
                              <div className="flex flex-wrap gap-2">
                                <Badge tone="accent" className="bg-forge-accent/20 border-forge-accent/30 text-forge-accent">{project.category}</Badge>
                                <Badge tone="red">{project.video_format === "shorts" ? "Shorts" : "Long Video"}</Badge>
                                <Badge tone={project.video_length === "auto" ? "accent" : "default"}>{project.video_length}</Badge>
                                <Badge tone="default" className="capitalize">{project.language}</Badge>
                                <Badge tone="accent">{project.current_stage}</Badge>
                                <Badge tone={project.status === "complete" ? "green" : "default"}>{project.status}</Badge>
                              </div>
                              <div className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-wider text-zinc-600">
                                {new Date(project.created_at).toLocaleDateString()} • {new Date(project.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                              </div>
                            </div>
                            <ArrowRight className="mt-1 h-5 w-5 text-zinc-700 transition-all group-hover:translate-x-1 group-hover:text-forge-red" />
                          </div>
                        </Link>
                        <button
                          className="absolute right-5 top-1/2 -translate-y-1/2 flex h-8 w-8 items-center justify-center rounded-lg text-zinc-700 hover:bg-forge-red/10 hover:text-forge-red transition-all duration-200"
                          title="Delete project"
                          onClick={(e) => {
                            e.preventDefault();
                            deleteProject(project.id);
                          }}
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </motion.div>
                    ))
                  )}
                </AnimatePresence>
              </div>
            </Panel>
          </motion.div>
        </section>
      </div>
    </main>
  );
}
