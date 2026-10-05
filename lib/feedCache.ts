import { uploadFeedCache } from "./blob";
import { getFeedCachePointer, setFeedCachePointer, type FeedCachePointer } from "./kv";
import { parseFeed } from "./pythonCompute";

const DEFAULT_TTL_SECONDS = 6 * 60 * 60; // re-download the (tens-of-MB) feed at most every 6h

/**
 * Returns a pointer to the cached slug -> active URL snapshot in Blob, downloading and
 * parsing the feed only when the cached copy is missing or stale.
 *
 * Only the pointer is handed to the compute function, never the map itself: the map is
 * several MB, and Vercel Functions reject request bodies above 4.5 MB
 * (FUNCTION_PAYLOAD_TOO_LARGE). The compute function fetches the snapshot from Blob and
 * keeps it in memory across batches.
 */
export async function getFeedSnapshot(xmlUrl: string): Promise<FeedCachePointer> {
  const ttlSeconds = Number(process.env.FEED_CACHE_TTL_SECONDS ?? DEFAULT_TTL_SECONDS);
  const pointer = await getFeedCachePointer();
  const ageSeconds = pointer ? (Date.now() - pointer.cachedAt) / 1000 : Infinity;

  if (pointer && ageSeconds < ttlSeconds) {
    return pointer;
  }

  const { slug_to_url } = await parseFeed(xmlUrl);
  const freshPointer = { blobUrl: await uploadFeedCache(slug_to_url), cachedAt: Date.now() };
  await setFeedCachePointer(freshPointer);
  return freshPointer;
}
