import { NextResponse } from "next/server";
import { uploadJobResult } from "@/lib/blob";
import { getSlugToUrl } from "@/lib/feedCache";
import { getJob, saveJob } from "@/lib/kv";
import { computeProgress } from "@/lib/progress";
import { finalize as finalizeCompute, httpCheckBatch, matchBatch } from "@/lib/pythonCompute";

const MATCH_BATCH_SIZE = 150;
const HTTP_CHECK_BATCH_SIZE = 60;

// Upper bound; the actual cap is whatever the Vercel plan in use allows (e.g. Hobby caps
// lower than this). Batch sizes above are tuned to stay well under a short timeout regardless.
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
      const slugToUrl = await getSlugToUrl(job.config.xml_url);
      const { state } = await matchBatch(job.state, slugToUrl, job.config, MATCH_BATCH_SIZE);
      job.state = state;
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
