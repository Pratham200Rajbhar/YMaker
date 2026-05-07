export type VideoFormat = "shorts" | "long";
export type WorkflowStage = "script" | "scenes" | "clips" | "voiceover" | "render";

export type Script = {
  id: number;
  version: number;
  video_script: string;
  on_screen_notes: string;
  title_suggestions: string[];
  estimated_duration: string;
  tone: string;
  approved: boolean;
};

export type Clip = {
  id: number;
  pexels_id: string;
  url: string;
  preview_url: string | null;
  image_url: string | null;
  width: number | null;
  height: number | null;
  duration: number | null;
  selected: boolean;
  local_path: string | null;
};

export type Scene = {
  id: number;
  scene_index: number;
  description: string;
  visual_keyword: string;
  duration_seconds: number;
  voiceover_text: string;
  approved: boolean;
  clips: Clip[];
};

export type Render = {
  id: number;
  voiceover_path: string | null;
  voice_name: string | null;
  voiceover_approved: boolean;
  subtitle_path: string | null;
  render_path: string | null;
  render_status: string;
  error_message: string | null;
};

export type Project = {
  id: number;
  title: string;
  idea: string;
  video_format: VideoFormat;
  language: string;
  current_stage: WorkflowStage;
  status: string;
  error_message: string | null;
  created_at: string;
  updated_at: string;
  latest_script: Script | null;
  scenes: Scene[];
  render: Render | null;
};

export type ProjectListItem = {
  id: number;
  title: string;
  video_format: VideoFormat;
  language: string;
  current_stage: WorkflowStage;
  status: string;
  created_at: string;
};
