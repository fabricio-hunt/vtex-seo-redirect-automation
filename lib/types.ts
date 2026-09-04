/** Hard floor for match confidence, mirrored from core/config.py MIN_MATCH_SCORE. The Python
 * pipeline enforces this server-side regardless of what a client sends, so this constant is
 * only used to keep the upload form from suggesting a weaker threshold is possible. */
export const MIN_MATCH_SCORE = 80;

export interface RecoveryConfig {
  xml_url: string;
  base_domain: string;
  legacy_redirect: string;
  threshold: number;
  check_http_status: boolean;
  max_workers: number;
  http_timeout: number;
  user_agent: string;
}

export const DEFAULT_CONFIG: RecoveryConfig = {
  xml_url: "http://www.bemol.com.br/XMLData/googleshopping.xml",
  base_domain: "https://www.bemol.com.br",
  legacy_redirect: "/superoferta",
  threshold: 90,
  check_http_status: true,
  max_workers: 10,
  http_timeout: 10,
  user_agent:
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
};

/** Fields the upload form is allowed to override; everything else keeps the default. */
export interface UserConfigInput {
  xml_url?: string;
  threshold?: number;
  check_http_status?: boolean;
  max_workers?: number;
}

export type JobPhase = "matching" | "http_check" | "done";

export interface JobState {
  phase: JobPhase;
  rows: string[];
  next_row_index: number;
  results: Array<{
    from: string;
    to: string;
    type: string;
    endDate: string;
    match_type: string;
    match_score?: number;
    status_code?: string | number;
  }>;
  unique_to_urls: string[];
  next_url_index: number;
  status_cache: Record<string, number | null>;
}

export type JobStatus = "running" | "done" | "error";

export interface JobStats {
  rows_total: number;
  valid_redirects: number;
  match_type_breakdown: Record<string, number>;
}

export interface JobRecord {
  id: string;
  createdAt: string;
  filename: string;
  config: RecoveryConfig;
  status: JobStatus;
  state: JobState;
  error?: string;
  resultUrls?: {
    redirects: string;
    review: string;
  };
  stats?: JobStats;
}

export interface JobProgress {
  phase: JobPhase;
  rows_total: number;
  rows_matched: number;
  urls_total: number;
  urls_checked: number;
  match_type_breakdown: Record<string, number>;
}

/** Shape returned by GET /backend/jobs/{id} — the job record without the heavy per-row state. */
export interface JobSummary {
  id: string;
  createdAt: string;
  filename: string;
  config: RecoveryConfig;
  status: JobStatus;
  error?: string;
  resultUrls?: { redirects: string; review: string };
  stats?: JobStats;
}

export interface JobDetailResponse extends JobSummary {
  progress: JobProgress;
}
