# Automated 404 URL Recovery for VTEX

## Overview

The **Automated 404 URL Recovery for VTEX** is a specialized tool designed to intelligently map broken (404) URLs to active product pages by cross-referencing legacy URLs with a live Google Shopping XML feed. This project significantly improves SEO performance, reduces crawl errors in Google Search Console, and enhances user experience by automatically generating `301 Moved Permanently` redirects.

## Features

- **Legacy Linx Rule**: Automatically detects legacy URLs containing `-p12345` and redirects them to the `/superoferta` landing page.
- **Exact Slug Matching**: Extracts slugs from 404 URLs and strictly matches them to the live active slugs from the Google Shopping feed.
- **Fuzzy Text Matching**: Uses advanced string similarity algorithms (Levenshtein Distance) to find the closest active product when the URL structure has slightly changed, employing a default `90%` similarity threshold to ensure high accuracy. Candidates whose slugs disagree on a numeric token (model number, screen size, storage, etc.) are rejected even if the text is otherwise very similar, e.g. `smart-tv-lg-50-polegadas` is never matched to `smart-tv-lg-55-polegadas`.
- **Minimum Accuracy Floor**: No match — regardless of type (Legacy/Exact/Fuzzy) — reaches the final diagnostic below a `match_score` of `80%`. This floor is enforced server-side (`core/config.MIN_MATCH_SCORE`) and cannot be lowered by the `--threshold` CLI flag or the web UI.
- **Infinite Loop Prevention**: Automatically detects if a source URL maps to the exact same destination path (`from == to`) and prevents same-URL redirects (`Same_URL_Ignored`), avoiding `ERR_TOO_MANY_REDIRECTS` redirect loops.
- **HTTP 200 Verification**: Concurrently checks the HTTP status code of destination URLs and filters the final export so that **only valid HTTP 200 destinations** are included in the VTEX redirect file.
- **CSV Output Generation**: Exports the redirect mappings conforming to the VTEX platform template format (`from;to;type;endDate`), ready for immediate import, alongside a detailed review audit file (`_review.csv`).

## How It Works

1. **Feed Ingestion**: The script downloads and parses the latest `googleshopping.xml` feed, extracting all active URLs and isolating product slugs.
2. **404 List Processing**: Reads broken URL reports (Excel/CSV format) located in the `404-gsc/` folder (defaulting to `404-gsc/Tabela.csv`).
3. **Smart Matching Engine**: Applies the matching rules sequentially: Legacy Check -> Exact Match -> Fuzzy Match (≥ threshold, floor 80%), while ensuring no URL redirects to itself.
4. **HTTP Status Verification**: Uses multithreaded requests (`ThreadPoolExecutor`) to verify that each matched destination URL returns an HTTP 200 status code.
5. **Export**: Generates `redirects.csv` containing only verified HTTP 200 redirects that scored at least `MIN_MATCH_SCORE` (80%) for VTEX, and `redirects_review.csv` with full diagnostics (`match_type`, `match_score`, and `status_code`) for SEO audit.

## Project layout

- `core/` — the matching engine, as a plain Python package with no web/CLI concerns: `config.py` (tunable `RecoveryConfig`), `feed.py` (feed download/parsing), `text_utils.py` (encoding fixes), `matching.py` (the 3 matching rules), `http_check.py` (HTTP 200 verification), `export.py` (CSV output), and `pipeline.py` (orchestration — both a one-shot `process_404_list` and a resumable, batched version used by the web job runner).
- `cli.py` — command-line entry point (replaces the old `url_recovery.py` script).
- `api/index.py` — a stateless FastAPI function wrapping `core/` in small, JSON-in/JSON-out compute steps (parse the feed, match a batch of rows, check a batch of URLs, finalize). It holds no state itself; the Next.js backend below calls it repeatedly and persists the result. Deployed as a Vercel Python serverless function, sibling to the Next.js app (Vercel auto-detects `api/*.py`).
- `app/`, `lib/`, `proxy.ts` — the Next.js app: upload/progress/history pages, plus route handlers under `app/backend/*` that own persistence (Vercel Blob for files/results, Upstash Redis for job records) and orchestrate calls to `api/index.py`. `proxy.ts` gates every page/route behind a shared-password login.
- `tests/` — pytest suite covering `core/` and `api/`.

### Why two backends?

The matching pipeline is genuinely slow (a ~38MB feed download, fuzzy-matching hundreds of rows, checking HTTP status of hundreds of destination URLs) — far longer than a single serverless function invocation should run, especially on Vercel's Hobby plan. So the work is split: `api/index.py` does one bounded chunk of computation per call and returns immediately; the Next.js backend is what remembers where a job is and keeps calling `api/index.py` until it's done, via `POST /backend/jobs/:id/advance` (called repeatedly by the browser while a job page is open).

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/fabricio-hunt/vtex-seo-redirect-automation.git
   cd vtex-seo-redirect-automation
   ```
2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   # On Windows:
   .\venv\Scripts\activate
   # On Linux/Mac:
   source venv/bin/activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

### CLI

Place your Google Search Console 404 CSV export in the `404-gsc/` directory (e.g., `404-gsc/Tabela.csv`) and run:

```bash
python cli.py
```

Parameters that used to be hardcoded are now flags — run `python cli.py --help` for the full list (`--input`, `--output-dir`, `--xml-url`, `--threshold`, `--no-http-check`, `--max-workers`).

The script will generate the files inside the `output/` directory:
- `output/redirects.csv`: Final VTEX import template (`from;to;type;endDate`) containing only verified HTTP 200 targets.
- `output/redirects_review.csv`: Full audit file including match scores, HTTP status codes, and ignored same-URL matches.

### Web

A web UI for uploading a spreadsheet and running a recovery job, with live progress and run history, lives under `app/` (Next.js) + `api/index.py` (FastAPI).

#### Local development

You need both processes running:

```bash
# Terminal 1 — Python compute function
pip install -r requirements.txt
uvicorn api.index:app --reload --port 8000

# Terminal 2 — Next.js app
npm install
npm run dev
```

Copy `.env.example` to `.env.local` and fill in `APP_PASSWORD`, `SESSION_SECRET`, and `INTERNAL_API_TOKEN` (any random strings for local dev — e.g. `openssl rand -hex 32`). `PYTHON_API_BASE_URL=http://localhost:8000` (already the default) points the Next.js backend at the local FastAPI process.

**Testing without real Vercel Blob / Upstash Redis:** set `LOCAL_DEV_STORAGE=true` in `.env.local`. Uploaded files, job records and the feed cache are then written to `.local-data/` on disk (`lib/localStore.ts`) instead of calling the real cloud services, so the full upload → progress → download → history flow works with zero cloud setup. **Never set this in a real deployment** — on Vercel each request can land on a different, ephemeral container, so anything written this way would vanish between steps of the same job. Switch it back to `false` (or unset it) once you've provisioned real Blob/Redis and want to test against them.

#### Deploying to Vercel

1. Push this repo to GitHub/GitLab/Bitbucket and import it in the Vercel dashboard (or `vercel` CLI). Root Directory should be the repo root — it contains both the Next.js app (`app/`, `package.json`) and the Python function (`api/index.py`), which Vercel deploys side by side with no extra config.
2. **Storage** (Project → Storage):
   - Add a **Blob** store and connect it to the project → sets `BLOB_READ_WRITE_TOKEN` automatically.
   - Add **Upstash for Redis** (Marketplace integration) and connect it → sets `UPSTASH_REDIS_REST_URL` / `UPSTASH_REDIS_REST_TOKEN` automatically.
3. **Environment variables** (Project → Settings → Environment Variables), generate each with e.g. `openssl rand -hex 32`:
   - `APP_PASSWORD` — the shared login password.
   - `SESSION_SECRET` — signs the login cookie.
   - `INTERNAL_API_TOKEN` — shared secret the Next.js backend sends to `api/index.py`. This matters: Python functions are *not* covered by `proxy.ts`, so without this check `api/index.py` would be reachable by anyone with the deployment URL.
4. Deploy. Check the Function logs for both the Next.js routes and `api/index.py` after your first real run.
5. **Verify the timeout budget for your plan.** This was built assuming the Hobby plan's short per-invocation timeout, so `app/backend/jobs/[id]/advance/route.ts` processes work in small batches (150 rows / 60 URLs per call) rather than all at once. Confirm in the Vercel dashboard what `maxDuration` your plan actually allows (declared as 60s in `vercel.json` / `export const maxDuration`, but plans cap this differently) and shrink the batch sizes in `advance/route.ts` if a call is timing out — most likely candidate is the very first `parse-feed` call for a fresh feed cache, since it downloads the full ~38MB feed in one shot.

#### A note on result file access

Downloaded CSVs (`redirects.csv`, `review.csv`) and the cached feed are stored in Vercel Blob with public, unguessable URLs. The app itself is gated by login, but anyone who obtains one of those exact URLs (e.g. from logs) could fetch that one file without logging in. Acceptable for an internal tool, but worth knowing.

## Testing

- **Python** (`core/` matching logic + `api/index.py` compute endpoints): `pytest tests/`.
- **Web** (`app/`, `lib/`): `npm run build` — Next.js type-checks the whole app as part of the production build; there's no separate `tsc --noEmit` step needed.

## Continuous Integration

A GitHub Actions workflow (`.github/workflows/ci.yml`) runs both of the above — the `pytest` suite and the Next.js build — on every `push` and `pull_request` to `main`/`master`.

## Notes

- `AGENTS.md` / `CLAUDE.md` at the repo root are auto-generated by `next dev` (Next.js 16 writes agent-facing notes about its own breaking changes) — regenerated on every dev run, safe to ignore or commit.

## Contribution & Trust

Built for VTEX store administrators and technical SEO specialists who need a reliable, data-driven approach to URL recovery. Contributions are welcome!
