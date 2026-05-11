import type { Project, ProjectListItem, Script, Scene, VideoFormat, VideoLength, Settings } from "./types";
import { logger } from "./logger";

export const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

const MAX_RETRIES = 2;
const RETRY_DELAY_MS = 800;

async function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let lastError: Error | null = null;

  for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
    try {
      const res = await fetch(`${API_BASE}${path}`, {
        ...init,
        headers: {
          "Content-Type": "application/json",
          ...(init?.headers ?? {}),
        },
        cache: "no-store",
      });

      if (!res.ok) {
        const body = await res.json().catch(() => ({ detail: res.statusText }));
        const errorMsg = body.detail ?? `HTTP ${res.status}: ${res.statusText}`;
        logger.error(`API Request failed: ${init?.method ?? "GET"} ${path}`, {
          status: res.status,
          statusText: res.statusText,
          error: errorMsg,
          attempt,
        });
        throw new Error(errorMsg);
      }

      // Handle 204 No Content and empty body responses
      if (res.status === 204) {
        return undefined as T;
      }
      const text = await res.text();
      if (!text) {
        return undefined as T;
      }
      return JSON.parse(text) as T;
    } catch (err) {
      lastError = err instanceof Error ? err : new Error(String(err));
      // Don't retry client errors (4xx) except 408/429
      if (err instanceof Error && err.message.includes("HTTP 4")) {
        const status = parseInt(err.message.match(/HTTP (\d+)/)?.[1] ?? "0", 10);
        if (status !== 408 && status !== 429) {
          throw err;
        }
      }
      if (attempt < MAX_RETRIES) {
        await sleep(RETRY_DELAY_MS * (attempt + 1));
      }
    }
  }

  throw lastError ?? new Error("Request failed after retries");
}

export const api = {
  listProjects: () => request<ProjectListItem[]>("/projects"),
  listCategories: () => request<string[]>("/categories"),
  createProject: (idea: string, category: string, video_format: VideoFormat, video_length: VideoLength, language: string, subtitles_enabled: boolean, subtitle_language: string) =>
    request<Project>("/projects", { method: "POST", body: JSON.stringify({ idea, category, video_format, video_length, language, subtitles_enabled, subtitle_language }) }),
  getProject: (id: number) => request<Project>(`/projects/${id}`),
  deleteProject: (id: number) => request<void>(`/projects/${id}`, { method: "DELETE" }),
  optimizeIdea: (idea: string) =>
    request<{ optimized_idea: string }>("/ai/optimize-idea", {
      method: "POST",
      body: JSON.stringify({ idea }),
    }),
  optimizeKeyword: (description: string, keyword: string) =>
    request<{ optimized_keyword: string }>("/ai/optimize-keyword", {
      method: "POST",
      body: JSON.stringify({ description, keyword }),
    }),

  generateScript: (id: number) =>
    request<Project>(`/projects/${id}/script/generate`, { method: "POST" }),
  saveScript: (id: number, script: Omit<Script, "id" | "version" | "approved">) =>
    request<Project>(`/projects/${id}/script`, { method: "PUT", body: JSON.stringify(script) }),
  approveScript: (id: number) =>
    request<Project>(`/projects/${id}/script/approve`, { method: "POST" }),

  generateScenes: (id: number) =>
    request<Project>(`/projects/${id}/scenes/generate`, { method: "POST" }),
  saveScene: (projectId: number, scene: Scene) =>
    request<Project>(`/projects/${projectId}/scenes/${scene.id}`, {
      method: "PUT",
      body: JSON.stringify(scene),
    }),
  approveScenes: (id: number) =>
    request<Project>(`/projects/${id}/scenes/approve`, { method: "POST" }),

  fetchClips: (id: number) =>
    request<Project>(`/projects/${id}/clips/fetch`, { method: "POST" }),
  selectClip: (projectId: number, sceneId: number, clipId: number) =>
    request<Project>(`/projects/${projectId}/clips/${sceneId}/select/${clipId}`, { method: "POST" }),
  approveClips: (id: number) =>
    request<Project>(`/projects/${id}/clips/approve`, { method: "POST" }),
  autoSelectClips: (id: number) =>
    request<Project>(`/projects/${id}/clips/auto-select`, { method: "POST" }),

  generateVoiceover: (id: number, voice_name: string) =>
    request<Project>(`/projects/${id}/voiceover/generate`, {
      method: "POST",
      body: JSON.stringify({ voice_name }),
    }),
  approveVoiceover: (id: number) =>
    request<Project>(`/projects/${id}/voiceover/approve`, { method: "POST" }),


  startRender: (id: number) =>
    request<Project>(`/projects/${id}/render/start`, { method: "POST" }),

  // Settings
  getSettings: () => request<Settings>("/settings"),
  updateSettings: (payload: Partial<Settings>) => request<Settings>("/settings", { method: "PUT", body: JSON.stringify(payload) }),
  testLLMConnection: () => request<{ provider: string, success: boolean, error: string | null }>("/settings/test", { method: "POST" }),
};

export function mediaUrl(path: string | null | undefined): string | null {
  if (!path) return null;
  if (path.startsWith("http")) return path;
  return `${API_BASE}${path}`;
}
