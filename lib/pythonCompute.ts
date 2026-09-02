import type { JobProgress, JobState, RecoveryConfig } from "./types";

/**
 * Calls the stateless Python compute function (api/index.py). Both it and this
 * Next.js app are deployed together, so on Vercel they share a domain — see
 * `pythonApiBase()`. Locally, run the FastAPI app separately
 * (`uvicorn api.index:app --reload --port 8000`) or via `vercel dev`, which
 * proxies both under the same local origin.
 */

function pythonApiBase(): string {
  if (process.env.PYTHON_API_BASE_URL) return process.env.PYTHON_API_BASE_URL;
  if (process.env.VERCEL_URL) return `https://${process.env.VERCEL_URL}`;
  return "http://localhost:8000";
}

async function callCompute<T>(path: string, body: unknown): Promise<T> {
  const token = process.env.INTERNAL_API_TOKEN;
  if (!token) {
    throw new Error("INTERNAL_API_TOKEN is not configured on the server.");
  }

  const response = await fetch(`${pythonApiBase()}${path}`, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "x-internal-token": token,
    },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    const detail = await response.text().catch(() => "");
    throw new Error(`Compute call ${path} failed (${response.status}): ${detail}`);
  }

  return (await response.json()) as T;
}

export async function loadInput(filename: string, contentBase64: string): Promise<{ rows: string[] }> {
  return callCompute("/api/compute/load-input", { filename, content_base64: contentBase64 });
}

export async function parseFeed(xmlUrl: string): Promise<{ slug_to_url: Record<string, string>; active_url_count: number }> {
  return callCompute("/api/compute/parse-feed", { xml_url: xmlUrl });
}

export async function matchBatch(
  state: JobState,
  slugToUrl: Record<string, string>,
  config: RecoveryConfig,
  batchSize = 150,
): Promise<{ state: JobState; progress: JobProgress }> {
  return callCompute("/api/compute/match-batch", { state, feed: { slug_to_url: slugToUrl }, config, batch_size: batchSize });
}

export async function httpCheckBatch(
  state: JobState,
  config: RecoveryConfig,
  batchSize = 60,
): Promise<{ state: JobState; progress: JobProgress }> {
  return callCompute("/api/compute/http-check-batch", { state, config, batch_size: batchSize });
}

export async function finalize(
  state: JobState,
  config: RecoveryConfig,
): Promise<{ redirects_csv: string; review_csv: string; stats: { rows_total: number; valid_redirects: number; match_type_breakdown: Record<string, number> } }> {
  return callCompute("/api/compute/finalize", { state, config });
}
