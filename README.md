# Automated 404 URL Recovery for VTEX

## Overview

The **Automated 404 URL Recovery for VTEX** is a specialized tool designed to intelligently map broken (404) URLs to active product pages by cross-referencing legacy URLs with a live Google Shopping XML feed. This project significantly improves SEO performance, reduces crawl errors in Google Search Console, and enhances user experience by automatically generating `301 Moved Permanently` redirects.

## Features

- **Legacy Linx Rule**: Automatically detects legacy URLs containing `-p12345` and redirects them to the `/superoferta` landing page.
- **Exact Slug Matching**: Extracts slugs from 404 URLs and strictly matches them to the live active slugs from the Google Shopping feed.
- **Fuzzy Text Matching**: Uses advanced string similarity algorithms (Levenshtein Distance) to find the closest active product when the URL structure has slightly changed, employing a strict `90%` similarity threshold to ensure high accuracy.
- **Infinite Loop Prevention**: Automatically detects if a source URL maps to the exact same destination path (`from == to`) and prevents same-URL redirects (`Same_URL_Ignored`), avoiding `ERR_TOO_MANY_REDIRECTS` redirect loops.
- **HTTP 200 Verification**: Concurrently checks the HTTP status code of destination URLs and filters the final export so that **only valid HTTP 200 destinations** are included in the VTEX redirect file.
- **CSV Output Generation**: Exports the redirect mappings conforming to the VTEX platform template format (`from;to;type;endDate`), ready for immediate import, alongside a detailed review audit file (`_review.csv`).

## How It Works

1. **Feed Ingestion**: The script downloads and parses the latest `googleshopping.xml` feed, extracting all active URLs and isolating product slugs.
2. **404 List Processing**: Reads broken URL reports (Excel/CSV format) located in the `404-gsc/` folder (defaulting to `404-gsc/Tabela.csv`).
3. **Smart Matching Engine**: Applies the matching rules sequentially: Legacy Check -> Exact Match -> Fuzzy Match (≥ 90%), while ensuring no URL redirects to itself.
4. **HTTP Status Verification**: Uses multithreaded requests (`ThreadPoolExecutor`) to verify that each matched destination URL returns an HTTP 200 status code.
5. **Export**: Generates `redirects.csv` containing only verified HTTP 200 redirects for VTEX, and `redirects_review.csv` with full diagnostics (`match_type` and `status_code`) for SEO audit.

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/fabricio-hunt/automated-404-url-recovery-for-vtex.git
   cd automated-404-url-recovery-for-vtex
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

Place your Google Search Console 404 CSV export in the `404-gsc/` directory (e.g., `404-gsc/Tabela.csv`) and run:

```bash
python url_recovery.py
```

The script will generate:
- `redirects.csv`: Final VTEX import template (`from;to;type;endDate`) containing only verified HTTP 200 targets.
- `redirects_review.csv`: Full audit file including match scores, HTTP status codes, and ignored same-URL matches.

## Testing

This project uses `pytest` for robust unit testing to ensure matching logic reliability and safety against loop redirects.

To run the test suite:
```bash
pytest tests/
```

## Continuous Integration

A GitHub Actions workflow is included (`.github/workflows/ci.yml`) which automatically runs the test suite on every `push` and `pull_request` to the `main` or `master` branches, ensuring code stability.

## Contribution & Trust

Built for VTEX store administrators and technical SEO specialists who need a reliable, data-driven approach to URL recovery. Contributions are welcome!
