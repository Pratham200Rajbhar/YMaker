"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, Settings as SettingsIcon, ShieldCheck, Cpu, Globe, Server, AlertCircle, CheckCircle2, Eye, EyeOff, Activity } from "lucide-react";
import { motion } from "framer-motion";

import { api } from "@/lib/api";
import { Settings } from "@/lib/types";
import { Button, Panel, inputClass, Badge, Field } from "@/components/ui";

export default function SettingsPage() {
  const router = useRouter();
  const [settings, setSettings] = useState<Settings | null>(null);
  const [busy, setBusy] = useState(false);
  const [testing, setTesting] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<{provider: string, success: boolean, error: string | null} | null>(null);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [showKeys, setShowKeys] = useState<{ [key: string]: boolean }>({});

  useEffect(() => {
    api.getSettings().then(setSettings).catch((err) => setError(err.message));
  }, []);

  async function updateProvider(providerId: string) {
    if (!settings) return;
    setBusy(true);
    setError("");
    setSuccess("");
    try {
      const updated = await api.updateSettings({ ...settings, llm_provider: providerId });
      setSettings(updated);
      setSuccess(`${providerId.toUpperCase()} set as active provider`);
      setTimeout(() => setSuccess(""), 3000);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update provider");
    } finally {
      setBusy(false);
    }
  }

  async function saveField(payload: Partial<Settings>) {
    if (!settings) return;
    try {
      const updated = await api.updateSettings(payload);
      setSettings(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Update failed");
    }
  }

  async function testConnection(providerId: string) {
    // We must ensure the settings are saved before testing if we changed them, 
    // but the instruction says the button calls POST /settings/test which uses current DB settings.
    // To be safe, let's save first if the active provider is being tested.
    setTesting(providerId);
    setTestResult(null);
    try {
      const res = await api.testLLMConnection();
      setTestResult({ provider: providerId, success: res.success, error: res.error });
    } catch (err) {
      setTestResult({ provider: providerId, success: false, error: err instanceof Error ? err.message : "Connection failed" });
    } finally {
      setTesting(null);
    }
  }

  const toggleKey = (key: string) => {
    setShowKeys(prev => ({ ...prev, [key]: !prev[key] }));
  };

  if (!settings) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-forge-bg">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-forge-red border-t-transparent" />
      </div>
    );
  }

  return (
    <main className="min-h-screen bg-forge-bg selection:bg-forge-red/30 selection:text-forge-red">
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
                <h1 className="text-2xl font-black tracking-tight text-white">LLM Providers</h1>
              </div>
              <p className="text-sm font-medium text-zinc-500">Configure your AI engine</p>
            </div>
          </div>
        </header>

        <div className="space-y-8">
          {error && (
            <div className="flex items-center gap-3 rounded-xl border border-forge-red/20 bg-forge-red/5 p-4 text-sm font-medium text-forge-red">
              <AlertCircle className="h-5 w-5" />
              {error}
            </div>
          )}
          {success && (
            <div className="flex items-center gap-3 rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-4 text-sm font-medium text-emerald-400">
              <CheckCircle2 className="h-5 w-5" />
              {success}
            </div>
          )}

          {/* OLLAMA */}
          <ProviderSection 
            id="ollama" 
            name="Ollama (Local)" 
            icon={Server}
            settings={settings}
            updateProvider={updateProvider}
            testConnection={testConnection}
            busy={busy}
            testing={testing}
            testResult={testResult}
          >
            <div className="grid gap-6 md:grid-cols-2">
              <Field label="Ollama Base URL">
                <input
                  className={inputClass}
                  value={settings.ollama_base_url}
                  onChange={(e) => setSettings({ ...settings, ollama_base_url: e.target.value })}
                  onBlur={() => saveField({ ollama_base_url: settings.ollama_base_url })}
                  placeholder="http://localhost:11434"
                />
              </Field>
              <Field label="Model Name">
                <input
                  className={inputClass}
                  value={settings.ollama_model}
                  onChange={(e) => setSettings({ ...settings, ollama_model: e.target.value })}
                  onBlur={() => saveField({ ollama_model: settings.ollama_model })}
                  placeholder="llama3"
                />
              </Field>
            </div>
          </ProviderSection>

          {/* OPENAI */}
          <ProviderSection 
            id="openai" 
            name="OpenAI" 
            icon={Cpu}
            settings={settings}
            updateProvider={updateProvider}
            testConnection={testConnection}
            busy={busy}
            testing={testing}
            testResult={testResult}
          >
            <div className="grid gap-6 md:grid-cols-2">
              <Field label="API Key">
                <div className="relative">
                  <input
                    type={showKeys.openai ? "text" : "password"}
                    className={`${inputClass} pr-10`}
                    value={settings.openai_api_key || ""}
                    onChange={(e) => setSettings({ ...settings, openai_api_key: e.target.value })}
                    onBlur={() => saveField({ openai_api_key: settings.openai_api_key })}
                    placeholder="sk-..."
                  />
                  <button 
                    onClick={() => toggleKey('openai')}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-zinc-500 hover:text-white"
                  >
                    {showKeys.openai ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
              </Field>
              <Field label="Model">
                <input
                  className={inputClass}
                  value={settings.openai_model}
                  onChange={(e) => setSettings({ ...settings, openai_model: e.target.value })}
                  onBlur={() => saveField({ openai_model: settings.openai_model })}
                  placeholder="gpt-4o"
                />
              </Field>
            </div>
          </ProviderSection>

          {/* OPENROUTER */}
          <ProviderSection 
            id="openrouter" 
            name="OpenRouter" 
            icon={Globe}
            settings={settings}
            updateProvider={updateProvider}
            testConnection={testConnection}
            busy={busy}
            testing={testing}
            testResult={testResult}
          >
            <div className="grid gap-6 md:grid-cols-2">
              <Field label="API Key">
                <div className="relative">
                  <input
                    type={showKeys.openrouter ? "text" : "password"}
                    className={`${inputClass} pr-10`}
                    value={settings.openrouter_api_key || ""}
                    onChange={(e) => setSettings({ ...settings, openrouter_api_key: e.target.value })}
                    onBlur={() => saveField({ openrouter_api_key: settings.openrouter_api_key })}
                    placeholder="sk-or-v1-..."
                  />
                  <button 
                    onClick={() => toggleKey('openrouter')}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-zinc-500 hover:text-white"
                  >
                    {showKeys.openrouter ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
              </Field>
              <Field label="Model">
                <input
                  className={inputClass}
                  value={settings.openrouter_model}
                  onChange={(e) => setSettings({ ...settings, openrouter_model: e.target.value })}
                  onBlur={() => saveField({ openrouter_model: settings.openrouter_model })}
                  placeholder="anthropic/claude-3.5-sonnet"
                />
              </Field>
            </div>
            <p className="text-[10px] font-medium text-zinc-500 italic">Browse models at <a href="https://openrouter.ai/models" target="_blank" className="text-forge-red hover:underline">openrouter.ai/models</a></p>
          </ProviderSection>

          {/* VERTEX */}
          <ProviderSection
            id="vertex"
            name="Google Vertex AI"
            icon={ShieldCheck}
            settings={settings}
            updateProvider={updateProvider}
            testConnection={testConnection}
            busy={busy}
            testing={testing}
            testResult={testResult}
          >
            <div className="grid gap-6 md:grid-cols-3">
              <Field label="Project ID">
                <input
                  className={inputClass}
                  value={settings.vertex_project_id || ""}
                  onChange={(e) => setSettings({ ...settings, vertex_project_id: e.target.value })}
                  onBlur={() => saveField({ vertex_project_id: settings.vertex_project_id })}
                  placeholder="your-project-id"
                />
              </Field>
              <Field label="Location">
                <input
                  className={inputClass}
                  value={settings.vertex_location}
                  onChange={(e) => setSettings({ ...settings, vertex_location: e.target.value })}
                  onBlur={() => saveField({ vertex_location: settings.vertex_location })}
                  placeholder="us-central1"
                />
              </Field>
              <Field label="Gemini Model">
                <input
                  className={inputClass}
                  value={settings.gemini_model}
                  onChange={(e) => setSettings({ ...settings, gemini_model: e.target.value })}
                  onBlur={() => saveField({ gemini_model: settings.gemini_model })}
                  placeholder="gemini-1.5-pro"
                />
              </Field>
            </div>
          </ProviderSection>

          {/* CLIP PROVIDER */}
          <Panel className="relative overflow-hidden border-white/10 bg-black/40">
            <div className="flex items-center justify-between mb-6 pb-4 border-b border-white/5">
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-lg bg-white/5 text-zinc-500">
                  <Globe className="h-5 w-5" />
                </div>
                <div>
                  <h2 className="text-xl font-bold text-white">Clip Provider</h2>
                  <p className="text-sm text-zinc-500">Default stock footage source for new projects</p>
                </div>
              </div>
            </div>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {[
                { value: "hybrid", label: "Hybrid (All Sources)" },
                { value: "free", label: "Free Only (Coverr + Mixkit)" },
                { value: "coverr", label: "Coverr.co (Free, CC0)" },
                { value: "mixkit", label: "Mixkit (Free)" },
                { value: "pexels", label: "Pexels (API key required)" },
                { value: "pixabay", label: "Pixabay (API key required)" },
              ].map((option) => (
                <button
                  key={option.value}
                  onClick={() => saveField({ clip_provider: option.value })}
                  className={`rounded-xl border px-4 py-3 text-left text-sm font-medium transition-all ${
                    settings.clip_provider === option.value
                      ? "border-forge-red bg-forge-red/10 text-white"
                      : "border-white/10 text-zinc-400 hover:border-white/20 hover:text-zinc-200"
                  }`}
                >
                  {option.label}
                </button>
              ))}
            </div>
          </Panel>
        </div>
      </div>
    </main>
  );
}

function ProviderSection({ icon: Icon, children, settings, updateProvider, testConnection, busy, testing, testResult, id, name }: {
  id: string;
  name: string;
  icon: React.ComponentType<{ className?: string }>;
  children: React.ReactNode;
  settings: Settings;
  updateProvider: (_id: string) => void;
  testConnection: (_id: string) => void;
  busy: boolean;
  testing: string | null;
  testResult: { provider: string; success: boolean; error: string | null } | null;
}) {
  const isActive = settings.llm_provider === id;
  return (
    <Panel className={`relative overflow-hidden border-white/10 transition-all duration-300 ${isActive ? "ring-2 ring-forge-red/50 bg-forge-red/[0.02]" : "bg-black/40"}`}>
      <div className="flex items-center justify-between mb-6 pb-4 border-b border-white/5">
        <div className="flex items-center gap-3">
          <div className={`p-2 rounded-lg ${isActive ? "bg-forge-red text-white" : "bg-white/5 text-zinc-500"}`}>
            <Icon className="h-5 w-5" />
          </div>
          <div>
            <h2 className="text-xl font-bold text-white">{name}</h2>
            <Badge tone={isActive ? "green" : "default"} className="mt-1">
              {isActive ? "Active" : "Inactive"}
            </Badge>
          </div>
        </div>
        <div className="flex gap-2">
          {!isActive && (
            <Button 
              className="bg-white/5 text-white hover:bg-white/10 px-3 py-1.5 text-xs min-h-8"
              onClick={() => updateProvider(id)}
              disabled={busy}
            >
              Set as Active
            </Button>
          )}
          <Button 
            className="border border-white/10 text-white hover:bg-white/5 px-3 py-1.5 text-xs min-h-8"
            onClick={() => testConnection(id)}
            busy={testing === id}
            disabled={!isActive}
            title={!isActive ? "Only the active provider can be tested" : ""}
          >
            <Activity className="h-4 w-4" />
            Test Connection
          </Button>
        </div>
      </div>

      <div className="space-y-6">
        {children}
      </div>

      {testResult && testResult.provider === id && (
        <motion.div 
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: "auto" }}
          className={`mt-6 p-4 rounded-xl border ${testResult.success ? "border-emerald-500/20 bg-emerald-500/5 text-emerald-400" : "border-forge-red/20 bg-forge-red/5 text-forge-red"}`}
        >
          <div className="flex items-center gap-2 font-bold text-sm">
            {testResult.success ? (
              <>
                <CheckCircle2 className="h-4 w-4" />
                Connected Successfully
              </>
            ) : (
              <>
                <AlertCircle className="h-4 w-4" />
                Connection Failed
              </>
            )}
          </div>
          {testResult.error && <p className="mt-1 text-xs opacity-80 font-mono">{testResult.error}</p>}
        </motion.div>
      )}
    </Panel>
  );
}
