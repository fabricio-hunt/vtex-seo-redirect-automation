import { NextResponse } from "next/server";
import { uploadJobResult } from "@/lib/blob";
import { getFreshFeedSnapshot, refreshFeedSnapshot } from "@/lib/feedCache";
import { getJob, saveJob } from "@/lib/kv";
import { computeProgress } from "@/lib/progress";
import { finalize as finalizeCompute, httpCheckBatch, matchBatch } from "@/lib/pythonCompute";

const MATCH_BATCH_SIZE = 150;
// Worst case per batch is ceil(batch / max_workers) rounds of `http_timeout` (10 workers,
// 10s by default): 20 URLs -> 2 rounds -> ~20s, leaving headroom under maxDuration even
// when the target site is slow. 60 URLs allowed 6 rounds -> ~60s and got the route killed.
const HTTP_CHECK_BATCH_SIZE = 20;

// Upper bound; the actual cap is whatever the Vercel plan in use allows (e.g. Hobby caps
// lower than this). Each invocation does exactly one bounded unit of work (a feed refresh,
// a matching batch or an HTTP-check batch) so it stays well under this regardless.
export const maxDuration = 60;

export async function POST(_request: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const job = await getJob(id);
  if (!job) {
    return NextResponse.json({ error: "Job não encontrado." }, { status: 404 });
  }
  if (job.status !== "running") {
    return NextResponse.json({ status: job.status, progress: computeProgress(job.state) });
  }

  try {
    if (job.state.phase === "matching") {
      const feedSnapshot = await getFreshFeedSnapshot();
      if (feedSnapshot) {
        const { state } = await matchBatch(job.state, feedSnapshot, job.config, MATCH_BATCH_SIZE);
        job.state = state;
      } else {
        // Refreshing the feed is a step of its own; the next advance call does the matching.
        await refreshFeedSnapshot(job.config.xml_url);
      }
    } else if (job.state.phase === "http_check") {
      const { state } = await httpCheckBatch(job.state, job.config, HTTP_CHECK_BATCH_SIZE);
      job.state = state;
    }

    if (job.state.phase === "done") {
      const result = await finalizeCompute(job.state, job.config);
      const [redirectsUrl, reviewUrl] = await Promise.all([
        uploadJobResult(id, "redirects.csv", result.redirects_csv),
        uploadJobResult(id, "review.csv", result.review_csv),
      ]);
      job.resultUrls = { redirects: redirectsUrl, review: reviewUrl };
      job.stats = result.stats;
      job.status = "done";
    }

    await saveJob(job);
    return NextResponse.json({ status: job.status, progress: computeProgress(job.state) });
  } catch (error) {
    job.status = "error";
    job.error = error instanceof Error ? error.message : "Erro desconhecido ao processar o job.";
    await saveJob(job);
    return NextResponse.json({ status: job.status, error: job.error }, { status: 500 });
  }
}
