import { Redis } from "@upstash/redis";
import { isLocalDevStorage, localKvGet, localKvSet, localKvZadd, localKvZrangeRev } from "./localStore";
import type { JobRecord } from "./types";

/**
 * Job records live in Upstash Redis (provisioned via the Vercel "Upstash for
 * Redis" marketplace integration, which sets UPSTASH_REDIS_REST_URL /
 * UPSTASH_REDIS_REST_TOKEN automatically), with a local-disk fallback for
 * development (see lib/localStore.ts). Each job is a JSON string at
 * `job:{id}`, indexed by creation time in the `jobs:index` sorted set so
 * the history page can page through them without a full SCAN.
 */

let client: Redis | null = null;

function redis(): Redis {
  if (!client) {
    client = Redis.fromEnv();
  }
  return client;
}

const jobKey = (id: string) => `job:${id}`;
const HISTORY_INDEX_KEY = "jobs:index";

export async function saveJob(job: JobRecord): Promise<void> {
  if (isLocalDevStorage()) {
    return localKvSet(jobKey(job.id), job);
  }
  await redis().set(jobKey(job.id), job);
}

export async function getJob(id: string): Promise<JobRecord | null> {
  if (isLocalDevStorage()) {
    return localKvGet<JobRecord>(jobKey(id));
  }
  return (await redis().get<JobRecord>(jobKey(id))) ?? null;
}

export async function addToHistory(id: string, createdAtMs: number): Promise<void> {
  if (isLocalDevStorage()) {
    return localKvZadd(HISTORY_INDEX_KEY, createdAtMs, id);
  }
  await redis().zadd(HISTORY_INDEX_KEY, { score: createdAtMs, member: id });
}

export async function listRecentJobIds(limit = 25, offset = 0): Promise<string[]> {
  if (isLocalDevStorage()) {
    return localKvZrangeRev(HISTORY_INDEX_KEY, offset, limit);
  }
  // Newest first.
  return redis().zrange<string[]>(HISTORY_INDEX_KEY, offset, offset + limit - 1, { rev: true });
}

const FEED_CACHE_POINTER_KEY = "feed:cache:pointer";

export interface FeedCachePointer {
  blobUrl: string;
  cachedAt: number;
}

export async function getFeedCachePointer(): Promise<FeedCachePointer | null> {
  if (isLocalDevStorage()) {
    return localKvGet<FeedCachePointer>(FEED_CACHE_POINTER_KEY);
  }
  return (await redis().get<FeedCachePointer>(FEED_CACHE_POINTER_KEY)) ?? null;
}

export async function setFeedCachePointer(pointer: FeedCachePointer): Promise<void> {
  if (isLocalDevStorage()) {
    return localKvSet(FEED_CACHE_POINTER_KEY, pointer);
  }
  await redis().set(FEED_CACHE_POINTER_KEY, pointer);
}
