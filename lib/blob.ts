import { put } from "@vercel/blob";
import { isLocalDevStorage, localBlobPut } from "./localStore";

/**
 * Thin wrapper around @vercel/blob, with a local-disk fallback for
 * development (see lib/localStore.ts). Requires a Blob store connected to
 * the project in production (BLOB_READ_WRITE_TOKEN set automatically once
 * connected via the Vercel dashboard). Uploaded files are addressable by
 * their returned URL — see the caveat in
 * app/backend/jobs/[id]/download/[file]/route.ts about what that means for
 * access control.
 */

export async function uploadJobInput(jobId: string, filename: string, bytes: Buffer): Promise<string> {
  const pathname = `jobs/${jobId}/input-${filename}`;
  if (isLocalDevStorage()) {
    return localBlobPut(pathname, bytes);
  }
  const blob = await put(pathname, bytes, { access: "public", addRandomSuffix: true });
  return blob.url;
}

export async function uploadJobResult(jobId: string, name: "redirects.csv" | "review.csv", csvText: string): Promise<string> {
  const pathname = `jobs/${jobId}/${name}`;
  if (isLocalDevStorage()) {
    return localBlobPut(pathname, csvText, "text/csv; charset=utf-8");
  }
  const blob = await put(pathname, csvText, {
    access: "public",
    addRandomSuffix: true,
    contentType: "text/csv; charset=utf-8",
  });
  return blob.url;
}

export async function uploadFeedCache(slugToUrl: Record<string, string>): Promise<string> {
  const pathname = "feed-cache/slug-to-url.json";
  const json = JSON.stringify(slugToUrl);
  if (isLocalDevStorage()) {
    return localBlobPut(pathname, json, "application/json");
  }
  const blob = await put(pathname, json, { access: "public", addRandomSuffix: true, contentType: "application/json" });
  return blob.url;
}

export async function fetchJson<T>(url: string): Promise<T> {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Failed to fetch ${url}: ${response.status}`);
  }
  return (await response.json()) as T;
}
