# Known Issues / Follow-up Items

Open items from the 2026-09-04 debugging session, to revisit later.

## 1. End-to-end confirmation of the double-encoding fix still pending

`core/text_utils.py::clean_text()` was fixed to fully resolve nested percent-encoding
(e.g. Google Search Console's `n%25C2%25B039` -> `n°39`), and verified live via a direct
`curl` call to `/api/compute/match-batch` against a freshly restarted uvicorn worker.

However, the two real VTEX imports the user ran (627 success / 200 failures, identical both
times) were both against a stale worker process that never actually picked up the fix
(`uvicorn --reload` logged "Reloading..." but silently kept serving the old code — see #2).

**Next step:** get a fresh upload/export from the now-genuinely-reloaded server, re-import
into VTEX, and confirm the failure count actually drops. If failures remain, capture the new
failing rows (they will differ from the ones already diagnosed) for a fresh root-cause pass.

## 2. `uvicorn --reload` is unreliable when the dev server is started by an agent (RESOLVED — root cause found, 2026-09-07)

Observed at least once: `--reload` detected a file change under `core/`, logged
"Reloading...", but never respawned the worker (process start time and PID were unchanged;
no "Started server process [PID]" line followed). This meant a committed fix was silently
not live for two full import cycles.

**Root cause confirmed 2026-09-07.** `.venv/Lib/site-packages/uvicorn/supervisors/basereload.py`
(`BaseReload.restart()`) does not kill the worker on Windows — it calls
`os.kill(self.process.pid, signal.CTRL_C_EVENT)`, which relies on `GenerateConsoleCtrlEvent`
being delivered through a real attached console, then blocks on `self.process.join()` waiting
for the worker to exit. Reproduced 4 times in a row (both `StatReload` and, after installing
`watchfiles`, `WatchFiles`; both with and without extra shell backgrounding/`disown`): the
event never reached/terminated the worker, the reloader thread hangs forever in `join()`, and
the *old* worker just keeps serving requests on the shared socket — silently, with no
exception logged. This is consistent with processes started by Claude Code's Bash/PowerShell
tools not having a real attached Windows console for `CTRL_C_EVENT` to target, regardless of
`--reload-dir` or reload backend. Not yet confirmed whether a normal, user-launched
interactive terminal (PowerShell/cmd window opened directly, not through an agent) is affected
the same way — plausible it isn't, since it has a real console.

**Decided approach:**
- Added `pid`, `started_at` (UTC ISO timestamp captured at import time), and `git_commit` to
  `GET /api/health` (`api/index.py`) — one curl call now proves whether a worker is stale,
  no process-inspection needed.
- `watchfiles` and `uvicorn` were added to `requirements.txt` (both were only present in the
  ad-hoc `.venv`, not pinned — `pip install -r requirements.txt` alone could not run the local
  server before this). `watchfiles` did **not** fix the underlying issue but is a strictly
  better reload backend than `StatReload` when reload *does* work, so kept.
- **Whenever Claude Code (or another agent) starts the local `uvicorn` server:** treat
  `--reload` as decorative. After any edit under `core/` or `api/`, manually find the PID
  listening on the port (`netstat -ano | grep LISTENING | grep :8000`), `taskkill //PID <pid> //T //F`,
  restart uvicorn, and confirm via `curl http://localhost:8000/api/health` that `started_at`
  changed before testing against it.
- Not yet tested: whether `--reload` works correctly for the user in their own normal
  interactive terminal. If it turns out console-attachment is really the deciding factor, no
  further fix is needed there — only agent-started servers need the manual-restart workflow
  above.

## 3. OneDrive-synced project directory is a standing corruption risk

The project lives under `OneDrive - BEMOL S A\Documentos\...`. This already caused one
confirmed `.local-data/kv.json` corruption (valid JSON + ~1MB NUL padding + truncated tail),
attributed to OneDrive grabbing the file mid-write during frequent job-progress polling.

Fixed for `kv.json` via write-to-temp-then-rename in `lib/localStore.ts`.

**Not yet fixed:** `localBlobPut()` in the same file (`lib/localStore.ts`) still writes job
CSVs and content-type sidecar files directly with `fs.writeFile()`, not atomically. These
files are written once per job phase rather than polled continuously, so the risk is lower,
but the same OneDrive-sync interference is theoretically possible.

**Next step:** either apply the same temp-then-rename pattern to `localBlobPut()`, or
consider excluding `.local-data/` from OneDrive sync (a `.onedrive-exclude` marker or moving
local dev storage outside the synced folder via an env-configurable root) to remove the root
cause entirely instead of mitigating it file-by-file.

## 4. Possible duplicate job activity from multiple browser tabs

The uvicorn access log around job `a5ffcacb-82f2-44d3-b86e-b8a64fcefe9c` showed interleaved
requests from two different client ports, consistent with two browser tabs polling the same
or different jobs concurrently. Not confirmed as a bug on its own (the atomic KV write from
#3 should prevent corruption either way), but worth a quick check with the user on whether
they routinely have multiple tabs open on this app, and whether the UI should guard against
or warn about concurrent job creation.

## 5. Re-verify there's no second root cause behind the VTEX import failures

Two real causes were found and fixed this session (duplicate `from` rows, double-encoded
`%C2%B0`-style artifacts). Both were strongly evidenced, but since the fixes were never
tested against a real VTEX import with the fresh server (see #1), it's not yet confirmed
that these were the *only* causes of the original 200 failing rows. Keep the original failing
CSV rows on hand for comparison once a new import result comes back.
