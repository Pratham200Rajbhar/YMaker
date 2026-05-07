import type { Project, ProjectListItem, Script, Scene, VideoFormat, VideoLength } from "./types";

export const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
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
    throw new Error(body.detail ?? "Request failed");
  }
  return res.json();
}

export const api = {
  listProjects: () => request<ProjectListItem[]>("/projects"),
  createProject: (idea: string, video_format: VideoFormat, video_length: VideoLength, language: string, subtitles_enabled: boolean, subtitle_language: string) =>
    request<Project>("/projects", { method: "POST", body: JSON.stringify({ idea, video_format, video_length, language, subtitles_enabled, subtitle_language }) }),
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
};

export function mediaUrl(path: string | null | undefined): string | null {
  if (!path) return null;
  if (path.startsWith("http")) return path;
  return `${API_BASE}${path}`;
}
