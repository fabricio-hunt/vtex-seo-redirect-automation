import type { JobProgress, JobState, RecoveryConfig } from "./types";

/**
 * Calls the local Python compute API (api/index.py), started next to this app by
 * scripts/start-local.mjs on 127.0.0.1:8000.
 */

function pythonApiBase(): string {
  return process.env.PYTHON_API_BASE_URL || "http://127.0.0.1:8000";
}

/**
 * Generous because nothing caps request duration locally; the first feed download (tens of
 * MB) is the slowest call. Still bounded so a hung compute call surfaces as a job error.
 */
const COMPUTE_TIMEOUT_MS = 5 * 60_000;

async function callCompute<T>(path: string, body: unknown): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${pythonApiBase()}${path}`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(COMPUTE_TIMEOUT_MS),
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "TimeoutError") {
      throw new Error(`Compute call ${path} timed out after ${COMPUTE_TIMEOUT_MS / 1000}s.`);
    }
    throw new Error(`Compute API unreachable at ${pythonApiBase()} (${path}): ${error instanceof Error ? error.message : error}`);
  }

  if (!response.ok) {
    const detail = await response.text().catch(() => "");
    throw new Error(`Compute call ${path} failed (${response.status}): ${detail}`);
  }

  return (await response.json()) as T;
}

export async function loadInput(filename: string, contentBase64: string): Promise<{ rows: string[] }> {
  return callCompute("/api/compute/load-input", { filename, content_base64: contentBase64 });
}

/** Downloads and parses the feed unless the compute API already has a fresh cached copy. */
export async function prepareFeed(xmlUrl: string): Promise<{ active_url_count: number; cached_at: number }> {
  return callCompute("/api/compute/prepare-feed", { xml_url: xmlUrl });
}

export async function matchBatch(
  state: JobState,
  config: RecoveryConfig,
  batchSize: number,
): Promise<{ state: JobState; progress: JobProgress }> {
  return callCompute("/api/compute/match-batch", { state, config, batch_size: batchSize });
}

export async function httpCheckBatch(
  state: JobState,
  config: RecoveryConfig,
  batchSize: number,
): Promise<{ state: JobState; progress: JobProgress }> {
  return callCompute("/api/compute/http-check-batch", { state, config, batch_size: batchSize });
}

export async function finalize(
  state: JobState,
  config: RecoveryConfig,
): Promise<{ redirects_csv: string; review_csv: string; stats: { rows_total: number; valid_redirects: number; match_type_breakdown: Record<string, number> } }> {
  return callCompute("/api/compute/finalize", { state, config });
}
