import { fetchJson, uploadFeedCache } from "./blob";
import { getFeedCachePointer, setFeedCachePointer } from "./kv";
import { parseFeed } from "./pythonCompute";

const DEFAULT_TTL_SECONDS = 6 * 60 * 60; // re-download the (tens-of-MB) feed at most every 6h

/**
 * Returns the slug -> active URL map for matching, downloading and parsing the feed
 * only when the cached copy (in Blob, pointed to from KV) is missing or stale.
 * This is what keeps most jobs from paying the full feed-download cost.
 */
export async function getSlugToUrl(xmlUrl: string): Promise<Record<string, string>> {
  const ttlSeconds = Number(process.env.FEED_CACHE_TTL_SECONDS ?? DEFAULT_TTL_SECONDS);
  const pointer = await getFeedCachePointer();
  const ageSeconds = pointer ? (Date.now() - pointer.cachedAt) / 1000 : Infinity;

  if (pointer && ageSeconds < ttlSeconds) {
    return fetchJson<Record<string, string>>(pointer.blobUrl);
  }

  const { slug_to_url } = await parseFeed(xmlUrl);
  const blobUrl = await uploadFeedCache(slug_to_url);
  await setFeedCachePointer({ blobUrl, cachedAt: Date.now() });
  return slug_to_url;
}
