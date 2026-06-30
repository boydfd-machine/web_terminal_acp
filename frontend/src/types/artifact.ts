export type TerminalArtifactStatus = "PENDING" | "RUNNING" | "SUCCEEDED" | "FAILED" | string;

export type TerminalArtifact = {
  id: string;
  client_id: string;
  virtual_window_id: string;
  source_window_id: string | null;
  ephemeral_window_id: string | null;
  artifact_scope: ArtifactScope;
  project_path: string | null;
  artifact_kind: string;
  title: string;
  status: TerminalArtifactStatus;
  content_json: Record<string, unknown> | null;
  display_html: string | null;
  metadata_json: Record<string, unknown> | null;
  last_error: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
};

export type PageReviewCard = {
  id: string;
  title: string;
  type: string;
  priority: "P0" | "P1" | "P2" | "P3" | string;
  severity: "critical" | "high" | "medium" | "low" | string;
  user_value: string;
  problem: string;
  proposal: string;
  evidence: Array<{ label: string; detail: string }>;
  acceptance_criteria: string[];
  test_notes: string[];
};

export type PageReviewCardsArtifactContent = {
  artifact_kind: "page_review_cards";
  title: string;
  page: string;
  review_scope: string;
  executive_summary: string;
  cards: PageReviewCard[];
  references?: Array<{ label: string; url?: string; note?: string }>;
};

export type ArtifactPluginPreviewStatus = "valid" | "invalid" | string;

export type ArtifactPluginPreview = {
  id: string;
  client_id: string;
  window_id: string;
  created_by_window_id: string;
  status: ArtifactPluginPreviewStatus;
  draft_artifact_kind: string | null;
  title: string;
  components_json: Record<string, unknown>;
  demo_content_json: Record<string, unknown> | null;
  rendered_content_json: Record<string, unknown> | null;
  display_html: string | null;
  last_error: string | null;
  created_at: string;
  updated_at: string;
  expires_at: string;
};

export type ArtifactPluginPreviewList = {
  window_id: string;
  previews: ArtifactPluginPreview[];
  total: number;
  limit: number;
  offset: number;
  has_more: boolean;
};

export type ArtifactPluginPreviewPayload = {
  client_id: string;
  window_id: string;
  title: string;
  python_source: string;
  prompt_template: string;
  html_template: string;
  json_schema: Record<string, unknown>;
  demo_content_json?: Record<string, unknown> | null;
};

export type ArtifactListItem =
  | { kind: "terminal_artifact"; id: string; artifact: TerminalArtifact }
  | { kind: "plugin_preview"; id: string; preview: ArtifactPluginPreview };

export type TerminalArtifactList = {
  window_id: string;
  artifact_scope: ArtifactScope;
  project_path: string | null;
  artifacts: TerminalArtifact[];
  total: number;
  limit: number;
  offset: number;
  has_more: boolean;
};

export type ProjectArtifactList = {
  project_path: string;
  artifacts: TerminalArtifact[];
  artifact_groups?: ProjectArtifactGroup[];
  total: number;
  limit: number;
  offset: number;
  has_more: boolean;
};

export type ProjectArtifactVersion = {
  artifact: TerminalArtifact;
  version_number: number;
  created_at: string;
  completed_at: string | null;
  source_window_id: string | null;
  source_window_title: string | null;
  virtual_window_title: string | null;
};

export type ProjectArtifactGroup = {
  artifact_kind: string;
  latest_artifact: TerminalArtifact;
  version_count: number;
  versions: ProjectArtifactVersion[];
};

export type ArtifactScope = "terminal" | "project";
export type ArtifactPluginDomain = ArtifactScope;
export type ArtifactPluginOrigin = "built_in" | "managed";
export type ArtifactPluginFormat = "legacy_python" | "template";

export type ArtifactPluginDescriptor = {
  domain: ArtifactPluginDomain;
  artifact_kind: string;
  label: string;
  default_title: string;
  origin: ArtifactPluginOrigin;
  editable: boolean;
  plugin_format: ArtifactPluginFormat;
  downloadable: boolean;
  path?: string | null;
  validation_error?: string | null;
};

export type ArtifactPluginList = {
  plugins: ArtifactPluginDescriptor[];
};

export type ArtifactPluginSource = ArtifactPluginDescriptor & {
  source?: string | null;
  python_source?: string | null;
  prompt_template?: string | null;
  html_template?: string | null;
  json_schema?: Record<string, unknown> | null;
  preview_content_json?: Record<string, unknown> | null;
  preview_content_json_by_locale?: Record<string, Record<string, unknown>> | null;
};

export type ArtifactPluginPayload = {
  source?: string | null;
  python_source?: string | null;
  prompt_template?: string | null;
  html_template?: string | null;
  json_schema?: Record<string, unknown> | null;
  preview_content_json?: Record<string, unknown> | null;
};
