import type { JobProgress, JobState } from "./types";

export function computeProgress(state: JobState): JobProgress {
  const breakdown: Record<string, number> = {};
  for (const row of state.results) {
    breakdown[row.match_type] = (breakdown[row.match_type] ?? 0) + 1;
  }
  return {
    phase: state.phase,
    rows_total: state.rows.length,
    rows_matched: state.next_row_index,
    urls_total: state.unique_to_urls.length,
    urls_checked: state.next_url_index,
    match_type_breakdown: breakdown,
  };
}
