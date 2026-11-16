import { NextResponse } from "next/server";
import { getJob, readJobFile } from "@/lib/jobStore";

const DOWNLOAD_NAMES = { redirects: "redirects.csv", review: "review.csv" } as const;

export async function GET(_request: Request, { params }: { params: Promise<{ id: string; file: string }> }) {
  const { id, file } = await params;
  if (file !== "redirects" && file !== "review") {
    return NextResponse.json({ error: "Arquivo inválido. Use 'redirects' ou 'review'." }, { status: 400 });
  }

  const job = await getJob(id);
  const stored = job?.status === "done" && job.resultFiles ? await readJobFile(job.resultFiles[file]) : null;
  if (!stored) {
    return NextResponse.json({ error: "Resultado ainda não disponível." }, { status: 404 });
  }

  return new NextResponse(new Uint8Array(stored.data), {
    headers: {
      "content-type": stored.contentType,
      "content-disposition": `attachment; filename="${DOWNLOAD_NAMES[file]}"`,
    },
  });
}
