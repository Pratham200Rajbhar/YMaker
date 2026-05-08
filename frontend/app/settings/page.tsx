"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, Save, Settings as SettingsIcon, ShieldCheck, Cpu, Globe, Server, AlertCircle, CheckCircle2 } from "lucide-react";
import { motion } from "framer-motion";

import { api } from "@/lib/api";
import { Settings } from "@/lib/types";
import { Button, Panel, inputClass, Badge, Field } from "@/components/ui";

const providers = [
  { id: "ollama", name: "Ollama", icon: Server, description: "Local LLM runner" },
  { id: "openai", name: "OpenAI", icon: Cpu, description: "GPT-4o & GPT-3.5" },
  { id: "openrouter", name: "OpenRouter", icon: Globe, description: "Unified LLM API" },
  { id: "vertex", name: "Vertex AI", icon: ShieldCheck, description: "Google Gemini Pro" },
];

export default function SettingsPage() {
  const router = useRouter();
  const [settings, setSettings] = useState<Settings | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  useEffect(() => {
    api.getSettings().then(setSettings).catch((err) => setError(err.message));
  }, []);

  async function saveSettings() {
    if (!settings) return;
    setBusy(true);
    setError("");
    setSuccess("");
    try {
      await api.updateSettings(settings);
      setSuccess("Settings updated successfully");
      setTimeout(() => setSuccess(""), 3000);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update settings");
    } finally {
      setBusy(false);
    }
  }

  if (!settings) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-forge-bg">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-forge-red border-t-transparent" />
      </div>
    );
  }

  return (
    <main className="min-h-screen bg-forge-bg selection:bg-forge-red/30 selection:text-forge-red">
      {/* Background Glow */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute -top-[10%] -left-[10%] w-[40%] h-[40%] bg-forge-red/5 rounded-full blur-[120px]" />
        <div className="absolute bottom-[10%] -right-[5%] w-[30%] h-[30%] bg-forge-accent/5 rounded-full blur-[100px]" />
      </div>

      <div className="relative mx-auto max-w-4xl px-6 py-12">
        <header className="mb-12 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <button
              onClick={() => router.push("/")}
              className="group flex h-10 w-10 items-center justify-center rounded-xl bg-white/5 text-zinc-400 border border-white/10 transition-all hover:bg-white/10 hover:text-white"
            >
              <ArrowLeft className="h-5 w-5 transition-transform group-hover:-translate-x-1" />
            </button>
            <div>
              <div className="flex items-center gap-2">
                <SettingsIcon className="h-5 w-5 text-forge-red" />
                <h1 className="text-2xl font-black tracking-tight text-white">System Settings</h1>
              </div>
              <p className="text-sm font-medium text-zinc-500">Configure AI models and API providers</p>
            </div>
          </div>
          <Button
            onClick={saveSettings}
            busy={busy}
            className="bg-gradient-to-r from-forge-red to-forge-red2 text-white shadow-lg shadow-forge-red/20"
          >
            <Save className="h-4 w-4" />
            Save Changes
          </Button>
        </header>

        <div className="space-y-8">
          {/* Provider Selection */}
          <section className="space-y-4">
            <div className="flex items-center gap-2 ml-1">
              <span className="text-[10px] font-bold uppercase tracking-widest text-zinc-500">Active Provider</span>
            </div>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {providers.map((p) => {
                const Icon = p.icon;
                const active = settings.llm_provider === p.id;
                return (
                  <button
                    key={p.id}
                    onClick={() => setSettings({ ...settings, llm_provider: p.id })}
                    className={`relative flex flex-col items-start gap-3 rounded-2xl border p-5 transition-all duration-300 ${
                      active
                        ? "border-forge-red bg-forge-red/5 ring-1 ring-forge-red/20"
                        : "border-white/5 bg-white/[0.02] hover:border-white/10 hover:bg-white/[0.04]"
                    }`}
                  >
                    <div className={`flex h-10 w-10 items-center justify-center rounded-xl ${
                      active ? "bg-forge-red text-white" : "bg-white/5 text-zinc-500"
                    }`}>
                      <Icon className="h-5 w-5" />
                    </div>
                    <div className="text-left">
                      <div className={`text-sm font-bold ${active ? "text-white" : "text-zinc-400"}`}>{p.name}</div>
                      <div className="mt-0.5 text-[10px] font-medium text-zinc-600">{p.description}</div>
                    </div>
                    {active && (
                      <div className="absolute top-3 right-3">
                        <div className="h-2 w-2 rounded-full bg-forge-red shadow-glow-red" />
                      </div>
                    )}
                  </button>
                );
              })}
            </div>
          </section>

          {/* Configuration Form */}
          <Panel className="relative overflow-hidden border-white/10 bg-black/40 backdrop-blur-xl">
            {settings.llm_provider === "ollama" && (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className="space-y-6"
              >
                <div className="flex items-center gap-2 pb-2 border-b border-white/5">
                  <Server className="h-4 w-4 text-forge-red" />
                  <h2 className="text-lg font-bold text-white">Ollama Configuration</h2>
                </div>
                <div className="grid gap-6 md:grid-cols-2">
                  <Field label="Base URL">
                    <input
                      className={inputClass}
                      value={settings.ollama_base_url}
                      onChange={(e) => setSettings({ ...settings, ollama_base_url: e.target.value })}
                      placeholder="http://localhost:11434"
                    />
                  </Field>
                  <Field label="Model Name">
                    <input
                      className={inputClass}
                      value={settings.ollama_model}
                      onChange={(e) => setSettings({ ...settings, ollama_model: e.target.value })}
                      placeholder="llama3, mistral, etc."
                    />
                  </Field>
                </div>
              </motion.div>
            )}

            {settings.llm_provider === "openai" && (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className="space-y-6"
              >
                <div className="flex items-center gap-2 pb-2 border-b border-white/5">
                  <Cpu className="h-4 w-4 text-forge-red" />
                  <h2 className="text-lg font-bold text-white">OpenAI Configuration</h2>
                </div>
                <div className="grid gap-6 md:grid-cols-2">
                  <Field label="API Key">
                    <input
                      type="password"
                      className={inputClass}
                      value={settings.openai_api_key || ""}
                      onChange={(e) => setSettings({ ...settings, openai_api_key: e.target.value })}
                      placeholder="sk-..."
                    />
                  </Field>
                  <Field label="Model Name">
                    <input
                      className={inputClass}
                      value={settings.openai_model}
                      onChange={(e) => setSettings({ ...settings, openai_model: e.target.value })}
                      placeholder="gpt-4o, gpt-4-turbo, etc."
                    />
                  </Field>
                </div>
              </motion.div>
            )}

            {settings.llm_provider === "openrouter" && (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className="space-y-6"
              >
                <div className="flex items-center gap-2 pb-2 border-b border-white/5">
                  <Globe className="h-4 w-4 text-forge-red" />
                  <h2 className="text-lg font-bold text-white">OpenRouter Configuration</h2>
                </div>
                <div className="grid gap-6 md:grid-cols-2">
                  <Field label="API Key">
                    <input
                      type="password"
                      className={inputClass}
                      value={settings.openrouter_api_key || ""}
                      onChange={(e) => setSettings({ ...settings, openrouter_api_key: e.target.value })}
                      placeholder="sk-or-v1-..."
                    />
                  </Field>
                  <Field label="Model Name">
                    <input
                      className={inputClass}
                      value={settings.openrouter_model}
                      onChange={(e) => setSettings({ ...settings, openrouter_model: e.target.value })}
                      placeholder="anthropic/claude-3.5-sonnet, etc."
                    />
                  </Field>
                </div>
              </motion.div>
            )}

            {settings.llm_provider === "vertex" && (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className="space-y-6"
              >
                <div className="flex items-center gap-2 pb-2 border-b border-white/5">
                  <ShieldCheck className="h-4 w-4 text-forge-red" />
                  <h2 className="text-lg font-bold text-white">Vertex AI Configuration</h2>
                </div>
                <div className="grid gap-6 md:grid-cols-3">
                  <Field label="Project ID">
                    <input
                      className={inputClass}
                      value={settings.vertex_project_id || ""}
                      onChange={(e) => setSettings({ ...settings, vertex_project_id: e.target.value })}
                      placeholder="your-project-id"
                    />
                  </Field>
                  <Field label="Location">
                    <input
                      className={inputClass}
                      value={settings.vertex_location}
                      onChange={(e) => setSettings({ ...settings, vertex_location: e.target.value })}
                      placeholder="us-central1"
                    />
                  </Field>
                  <Field label="Model Name">
                    <input
                      className={inputClass}
                      value={settings.gemini_model}
                      onChange={(e) => setSettings({ ...settings, gemini_model: e.target.value })}
                      placeholder="gemini-1.5-pro"
                    />
                  </Field>
                </div>
              </motion.div>
            )}
          </Panel>

          {/* Feedback Messages */}
          <div className="flex flex-col gap-3">
            {error && (
              <motion.div
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                className="flex items-center gap-3 rounded-xl border border-forge-red/20 bg-forge-red/5 p-4 text-sm font-medium text-forge-red"
              >
                <AlertCircle className="h-5 w-5 flex-shrink-0" />
                {error}
              </motion.div>
            )}
            {success && (
              <motion.div
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                className="flex items-center gap-3 rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-4 text-sm font-medium text-emerald-400"
              >
                <CheckCircle2 className="h-5 w-5 flex-shrink-0" />
                {success}
              </motion.div>
            )}
          </div>
        </div>
      </div>
    </main>
  );
}
