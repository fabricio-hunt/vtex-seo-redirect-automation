import { NextResponse } from "next/server";
import { getJob, saveJob, uploadJobResult } from "@/lib/jobStore";
import { computeProgress } from "@/lib/progress";
import { finalize as finalizeCompute, httpCheckBatch, matchBatch, prepareFeed } from "@/lib/pythonCompute";

// Each call does one bounded unit of work (feed preparation, a matching batch or an
// HTTP-check batch) so the job page can show progress between calls.
const MATCH_BATCH_SIZE = 1000;
// Worst case per batch is ceil(batch / max_workers) rounds of `http_timeout`
// (10 workers, 10s by default): 100 URLs -> ~100s, well under the compute call timeout.
const HTTP_CHECK_BATCH_SIZE = 100;

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
      if (job.feedPreparedAt) {
        const { state } = await matchBatch(job.state, job.config, MATCH_BATCH_SIZE);
        job.state = state;
      } else {
        // Downloading the feed is a step of its own; the next advance call does the matching.
        await prepareFeed(job.config.xml_url);
        job.feedPreparedAt = new Date().toISOString();
      }
    } else if (job.state.phase === "http_check") {
      const { state } = await httpCheckBatch(job.state, job.config, HTTP_CHECK_BATCH_SIZE);
      job.state = state;
    }

    if (job.state.phase === "done") {
      const result = await finalizeCompute(job.state, job.config);
      const [redirectsFile, reviewFile] = await Promise.all([
        uploadJobResult(id, "redirects.csv", result.redirects_csv),
        uploadJobResult(id, "review.csv", result.review_csv),
      ]);
      job.resultFiles = { redirects: redirectsFile, review: reviewFile };
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
