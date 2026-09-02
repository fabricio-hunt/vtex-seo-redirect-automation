import { NextResponse } from "next/server";
import { localBlobGet } from "@/lib/localStore";

/**
 * Serves files written by the local-dev storage fallback (lib/localStore.ts).
 * Only reachable behind auth (everything under /backend/* is gated by
 * proxy.ts) — doesn't exist in production, where real Vercel Blob URLs are
 * used instead.
 */
export async function GET(_request: Request, { params }: { params: Promise<{ path: string[] }> }) {
  const { path } = await params;
  const pathname = path.join("/");

  const file = await localBlobGet(pathname);
  if (!file) {
    return NextResponse.json({ error: "Arquivo não encontrado." }, { status: 404 });
  }

  return new NextResponse(new Uint8Array(file.data), {
    headers: { "content-type": file.contentType },
  });
}
