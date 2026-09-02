import { NextResponse } from "next/server";
import { getJob } from "@/lib/kv";

export async function GET(_request: Request, { params }: { params: Promise<{ id: string; file: string }> }) {
  const { id, file } = await params;
  const job = await getJob(id);
  if (!job || job.status !== "done" || !job.resultUrls) {
    return NextResponse.json({ error: "Resultado ainda não disponível." }, { status: 404 });
  }

  const url = file === "review" ? job.resultUrls.review : file === "redirects" ? job.resultUrls.redirects : null;
  if (!url) {
    return NextResponse.json({ error: "Arquivo inválido. Use 'redirects' ou 'review'." }, { status: 400 });
  }

  return NextResponse.redirect(url);
}
