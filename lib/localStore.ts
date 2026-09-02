import { promises as fs } from "fs";
import path from "path";

/**
 * File-based stand-in for Vercel Blob + Upstash Redis, used only for local
 * development so the app is testable without provisioning real cloud
 * storage first. Single-process, no locking — fine for one local `next dev`,
 * not a database.
 *
 * Opt-in via LOCAL_DEV_STORAGE=true (not inferred from "token missing") so a
 * real deployment that forgot to set BLOB_READ_WRITE_TOKEN / UPSTASH_* still
 * fails loudly instead of silently writing to an ephemeral /tmp that
 * disappears between serverless invocations.
 */

export function isLocalDevStorage(): boolean {
  return process.env.LOCAL_DEV_STORAGE === "true";
}

const ROOT = path.join(process.cwd(), ".local-data");
const BLOB_DIR = path.join(ROOT, "blob");
const KV_FILE = path.join(ROOT, "kv.json");

function localBaseUrl(): string {
  return process.env.LOCAL_APP_BASE_URL || "http://localhost:3000";
}

// --- blob-like file storage ---------------------------------------------

export async function localBlobPut(pathname: string, data: Buffer | string, contentType = "application/octet-stream"): Promise<string> {
  const filePath = path.join(BLOB_DIR, pathname);
  await fs.mkdir(path.dirname(filePath), { recursive: true });
  await fs.writeFile(filePath, data);
  await fs.writeFile(`${filePath}.contenttype`, contentType);
  return `${localBaseUrl()}/backend/local-files/${pathname}`;
}

export async function localBlobGet(pathname: string): Promise<{ data: Buffer; contentType: string } | null> {
  const filePath = path.join(BLOB_DIR, pathname);
  try {
    const data = await fs.readFile(filePath);
    const contentType = await fs.readFile(`${filePath}.contenttype`, "utf8").catch(() => "application/octet-stream");
    return { data, contentType };
  } catch {
    return null;
  }
}

// --- minimal KV (string get/set + sorted-set index) ----------------------

interface KvFile {
  strings: Record<string, unknown>;
  sortedSets: Record<string, Array<{ member: string; score: number }>>;
}

async function readKv(): Promise<KvFile> {
  try {
    return JSON.parse(await fs.readFile(KV_FILE, "utf8"));
  } catch {
    return { strings: {}, sortedSets: {} };
  }
}

async function writeKv(data: KvFile): Promise<void> {
  await fs.mkdir(ROOT, { recursive: true });
  await fs.writeFile(KV_FILE, JSON.stringify(data, null, 2));
}

export async function localKvSet(key: string, value: unknown): Promise<void> {
  const data = await readKv();
  data.strings[key] = value;
  await writeKv(data);
}

export async function localKvGet<T>(key: string): Promise<T | null> {
  const data = await readKv();
  return (data.strings[key] as T | undefined) ?? null;
}

export async function localKvZadd(key: string, score: number, member: string): Promise<void> {
  const data = await readKv();
  const set = (data.sortedSets[key] ?? []).filter((e) => e.member !== member);
  set.push({ member, score });
  data.sortedSets[key] = set;
  await writeKv(data);
}

export async function localKvZrangeRev(key: string, offset: number, limit: number): Promise<string[]> {
  const data = await readKv();
  const set = data.sortedSets[key] ?? [];
  return [...set]
    .sort((a, b) => b.score - a.score)
    .slice(offset, offset + limit)
    .map((e) => e.member);
}
