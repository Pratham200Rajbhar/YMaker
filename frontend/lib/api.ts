import type { Project, ProjectListItem, Script, Scene, VideoFormat, VideoLength, Settings, ImageProgress } from "./types";
import { logger } from "./logger";

export const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? (typeof window !== "undefined" ? `http://${window.location.hostname}:8000` : "http://localhost:8000");

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  const isFormData = init?.body instanceof FormData;

  if (!isFormData && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers,
    cache: "no-store",
  });

  if (!res.ok) {
    let errorDetail: any;
    try {
      errorDetail = await res.json();
    } catch {
      errorDetail = await res.text().catch(() => res.statusText);
    }

    let errorMsg = `HTTP ${res.status}: ${res.statusText}`;
    if (errorDetail && typeof errorDetail === "object" && errorDetail.detail) {
      errorMsg = Array.isArray(errorDetail.detail)
        ? errorDetail.detail.map((e: any) => e.msg).join(", ")
        : String(errorDetail.detail);
    } else if (typeof errorDetail === "string" && errorDetail) {
      errorMsg = errorDetail;
    }

    logger.error(`API Request failed: ${init?.method ?? "GET"} ${path}`, {
      status: res.status,
      statusText: res.statusText,
      error: errorDetail,
      message: errorMsg,
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
}

export const api = {
  listProjects: () => request<ProjectListItem[]>("/projects"),
  listCategories: () => request<string[]>("/categories"),
  createProject: (idea: string, category: string, video_format: VideoFormat, video_length: VideoLength, language: string, subtitles_enabled: boolean, subtitle_language: string) =>
    request<Project>("/projects", { method: "POST", body: JSON.stringify({ idea, category, video_format, video_length, language, subtitles_enabled, subtitle_language }) }),
  getProject: (id: number) => request<Project>(`/projects/${id}`),
  deleteProject: (id: number) => request<void>(`/projects/${id}`, { method: "DELETE" }),
  jumpToStage: (projectId: number, stage: WorkflowStage) => request<Project>(`/projects/${projectId}/jump/${stage}`, { method: "POST" }),
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

  // Image Story
  generateImagePrompts: (id: number) =>
    request<Project>(`/projects/${id}/image-scenes/generate-prompts`, { method: "POST" }),
  updateImagePrompt: (projectId: number, sceneId: number, data: { image_prompt: string; image_prompt_approved: boolean }) =>
    request<Scene>(`/projects/${projectId}/image-scenes/${sceneId}/prompt`, { method: "PUT", body: JSON.stringify(data) }),
  uploadSceneImage: (projectId: number, sceneId: number, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<Scene>(`/projects/${projectId}/image-scenes/${sceneId}/upload-image`, {
      method: "POST",
      body: form,
    });
  },
  uploadSceneImageByUrl: (projectId: number, sceneId: number, url: string) =>
    request<Scene>(`/projects/${projectId}/image-scenes/${sceneId}/upload-image-by-url`, {
      method: "POST",
      body: JSON.stringify({ url }),
    }),
  deleteSceneImage: (projectId: number, sceneId: number) =>
    request<Scene>(`/projects/${projectId}/image-scenes/${sceneId}/image`, { method: "DELETE" }),
  getImageProgress: (id: number) =>
    request<ImageProgress>(`/projects/${id}/image-scenes/progress`),
  assignSceneVoice: (projectId: number, sceneId: number, data: { character_voice: string }) =>
    request<Scene>(`/projects/${projectId}/image-scenes/${sceneId}/assign-voice`, { method: "PUT", body: JSON.stringify(data) }),
  approveImages: (id: number) =>
    request<Project>(`/projects/${id}/image-scenes/approve-images`, { method: "POST" }),
  generateMultiVoice: (id: number, data: { default_voice: string; scene_voices: Record<number, string> }) =>
    request<Project>(`/projects/${id}/voiceover/generate-multivoice`, { method: "POST", body: JSON.stringify(data) }),
  startImageStoryRender: (id: number) =>
    request<Project>(`/projects/${id}/render/start-image-story`, { method: "POST" }),

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
