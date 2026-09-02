import { randomUUID } from "crypto";
import { NextResponse } from "next/server";
import { uploadJobInput } from "@/lib/blob";
import { addToHistory, getJob, listRecentJobIds, saveJob } from "@/lib/kv";
import { loadInput } from "@/lib/pythonCompute";
import { DEFAULT_CONFIG, JobRecord, JobState, RecoveryConfig, UserConfigInput } from "@/lib/types";

export const maxDuration = 60;

function buildConfig(input: UserConfigInput): RecoveryConfig {
  return {
    ...DEFAULT_CONFIG,
    ...(input.xml_url ? { xml_url: input.xml_url } : {}),
    ...(typeof input.threshold === "number" && !Number.isNaN(input.threshold) ? { threshold: input.threshold } : {}),
    ...(typeof input.check_http_status === "boolean" ? { check_http_status: input.check_http_status } : {}),
    ...(typeof input.max_workers === "number" && !Number.isNaN(input.max_workers) ? { max_workers: input.max_workers } : {}),
  };
}

export async function POST(request: Request) {
  const form = await request.formData();
  const file = form.get("file");
  if (!(file instanceof File)) {
    return NextResponse.json({ error: "Envie um arquivo .csv ou .xlsx no campo 'file'." }, { status: 400 });
  }

  const config = buildConfig({
    xml_url: (form.get("xml_url") as string) || undefined,
    threshold: form.get("threshold") ? Number(form.get("threshold")) : undefined,
    check_http_status: form.has("check_http_status") ? form.get("check_http_status") === "true" : undefined,
    max_workers: form.get("max_workers") ? Number(form.get("max_workers")) : undefined,
  });

  const id = randomUUID();

  try {
    const bytes = Buffer.from(await file.arrayBuffer());
    await uploadJobInput(id, file.name, bytes);
    const { rows } = await loadInput(file.name, bytes.toString("base64"));

    const state: JobState = {
      phase: "matching",
      rows,
      next_row_index: 0,
      results: [],
      unique_to_urls: [],
      next_url_index: 0,
      status_cache: {},
    };

    const job: JobRecord = {
      id,
      createdAt: new Date().toISOString(),
      filename: file.name,
      config,
      status: "running",
      state,
    };

    await saveJob(job);
    await addToHistory(id, Date.now());

    return NextResponse.json({ id });
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Falha ao criar o job." },
      { status: 500 },
    );
  }
}

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const limit = Number(searchParams.get("limit") ?? 25);
  const offset = Number(searchParams.get("offset") ?? 0);

  const ids = await listRecentJobIds(limit, offset);
  const jobs = await Promise.all(ids.map((id) => getJob(id)));

  const summarized = jobs
    .filter((job): job is JobRecord => job !== null)
    .map((job) => ({
      id: job.id,
      createdAt: job.createdAt,
      filename: job.filename,
      config: job.config,
      status: job.status,
      error: job.error,
      resultUrls: job.resultUrls,
      stats: job.stats,
    }));

  return NextResponse.json({ jobs: summarized });
}
