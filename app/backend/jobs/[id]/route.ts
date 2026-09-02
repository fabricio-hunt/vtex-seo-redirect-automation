import { NextResponse } from "next/server";
import { getJob } from "@/lib/kv";
import { computeProgress } from "@/lib/progress";

export async function GET(_request: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const job = await getJob(id);
  if (!job) {
    return NextResponse.json({ error: "Job não encontrado." }, { status: 404 });
  }

  return NextResponse.json({
    id: job.id,
    createdAt: job.createdAt,
    filename: job.filename,
    config: job.config,
    status: job.status,
    error: job.error,
    resultUrls: job.resultUrls,
    stats: job.stats,
    progress: computeProgress(job.state),
  });
}
