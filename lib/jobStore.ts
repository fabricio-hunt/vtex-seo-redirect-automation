import { promises as fs } from "fs";
import path from "path";
import type { JobRecord } from "./types";

export type JobResultName = "redirects.csv" | "review.csv";

const ROOT = path.resolve(/*turbopackIgnore: true*/ process.env.LOCAL_DATA_DIR || path.join(process.cwd(), ".local-data"));
const BLOB_DIR = path.join(ROOT, "blob");
const KV_FILE = path.join(ROOT, "kv.json");
const HISTORY_INDEX_KEY = "jobs:index";

const jobKey = (id: string) => `job:${id}`;

async function writeFileAtomic(filePath: string, data: Buffer | string): Promise<void> {
  await fs.mkdir(path.dirname(filePath), { recursive: true });
  const tmpFile = `${filePath}.${process.pid}.${Date.now()}.tmp`;
  await fs.writeFile(tmpFile, data);
  await fs.rename(tmpFile, filePath);
}

function resolveBlobPath(pathname: string): string {
  const root = path.resolve(BLOB_DIR) + path.sep;
  const filePath = path.resolve(BLOB_DIR, pathname);
  if (!filePath.startsWith(root)) {
    throw new Error(`Refusing to access path outside blob storage: ${pathname}`);
  }
  return filePath;
}

// --- Blob storage (job inputs and results) ---

export async function uploadJobInput(jobId: string, filename: string, bytes: Buffer): Promise<string> {
  const pathname = `jobs/${jobId}/input-${filename}`;
  const filePath = resolveBlobPath(pathname);
  await writeFileAtomic(filePath, bytes);
  await writeFileAtomic(`${filePath}.contenttype`, "application/octet-stream");
  return pathname;
}

export async function uploadJobResult(jobId: string, name: JobResultName, csvText: string): Promise<string> {
  const pathname = `jobs/${jobId}/${name}`;
  const filePath = resolveBlobPath(pathname);
  await writeFileAtomic(filePath, csvText);
  await writeFileAtomic(`${filePath}.contenttype`, "text/csv; charset=utf-8");
  return pathname;
}

export async function readJobFile(pathname: string): Promise<{ data: Buffer; contentType: string } | null> {
  let filePath: string;
  try {
    filePath = resolveBlobPath(pathname);
  } catch {
    return null;
  }
  try {
    const data = await fs.readFile(/*turbopackIgnore: true*/ filePath);
    const contentType = await fs.readFile(`${filePath}.contenttype`, "utf8").catch(() => "application/octet-stream");
    return { data, contentType };
  } catch {
    return null;
  }
}

// --- KV storage (job metadata and history index) ---

interface KvFile {
  strings: Record<string, unknown>;
  sortedSets: Record<string, Array<{ member: string; score: number }>>;
}

async function readKv(): Promise<KvFile> {
  try {
    return JSON.parse(await fs.readFile(/*turbopackIgnore: true*/ KV_FILE, "utf8"));
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code !== "ENOENT") {
      console.error(`[jobStore] Failed to read ${KV_FILE}:`, error);
    }
    return { strings: {}, sortedSets: {} };
  }
}

async function writeKv(data: KvFile): Promise<void> {
  await writeFileAtomic(KV_FILE, JSON.stringify(data, null, 2));
}

export async function saveJob(job: JobRecord): Promise<void> {
  const data = await readKv();
  data.strings[jobKey(job.id)] = job;
  await writeKv(data);
}

export async function getJob(id: string): Promise<JobRecord | null> {
  const data = await readKv();
  return (data.strings[jobKey(id)] as JobRecord) ?? null;
}

export async function addToHistory(id: string, createdAtMs: number): Promise<void> {
  const data = await readKv();
  const set = data.sortedSets[HISTORY_INDEX_KEY] ?? [];
  const existing = set.findIndex((entry) => entry.member === id);
  if (existing >= 0) {
    set[existing].score = createdAtMs;
  } else {
    set.push({ member: id, score: createdAtMs });
  }
  set.sort((a, b) => a.score - b.score);
  data.sortedSets[HISTORY_INDEX_KEY] = set;
  await writeKv(data);
}

export async function listRecentJobIds(limit = 25, offset = 0): Promise<string[]> {
  const data = await readKv();
  const set = data.sortedSets[HISTORY_INDEX_KEY] ?? [];
  const reversed = [...set].reverse();
  return reversed.slice(offset, offset + limit).map((entry) => entry.member);
}

