import { uploadFeedCache } from "./blob";
import { getFeedCachePointer, setFeedCachePointer, type FeedCachePointer } from "./kv";
import { parseFeed } from "./pythonCompute";

const DEFAULT_TTL_SECONDS = 6 * 60 * 60; // re-download the (tens-of-MB) feed at most every 6h

/** Returns the cached feed snapshot pointer, or null when it is missing or stale. */
export async function getFreshFeedSnapshot(): Promise<FeedCachePointer | null> {
  const ttlSeconds = Number(process.env.FEED_CACHE_TTL_SECONDS ?? DEFAULT_TTL_SECONDS);
  const pointer = await getFeedCachePointer();
  const ageSeconds = pointer ? (Date.now() - pointer.cachedAt) / 1000 : Infinity;
  return pointer && ageSeconds < ttlSeconds ? pointer : null;
}

/**
 * Downloads and parses the feed, stores the slug -> active URL snapshot in Blob and
 * points the cache at it. This is the slowest single step (the feed is tens of MB), so
 * callers run it on its own instead of in the same invocation as a matching batch.
 *
 * Only the pointer is handed to the compute function, never the map itself: the map is
 * several MB, and Vercel Functions reject request bodies above 4.5 MB
 * (FUNCTION_PAYLOAD_TOO_LARGE). The compute function fetches the snapshot from Blob and
 * keeps it in memory across batches.
 */
export async function refreshFeedSnapshot(xmlUrl: string): Promise<FeedCachePointer> {
  const { slug_to_url } = await parseFeed(xmlUrl);
  const freshPointer = { blobUrl: await uploadFeedCache(slug_to_url), cachedAt: Date.now() };
  await setFeedCachePointer(freshPointer);
  return freshPointer;
}
