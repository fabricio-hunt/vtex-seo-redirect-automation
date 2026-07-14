# Automated 404 URL Recovery for VTEX

## Overview

The **Automated 404 URL Recovery for VTEX** is a specialized tool designed to intelligently map broken (404) URLs to active product pages by cross-referencing legacy URLs with a live Google Shopping XML feed. This project significantly improves SEO performance, reduces crawl errors in Google Search Console, and enhances user experience by automatically generating `301 Moved Permanently` redirects.

## Features

- **Legacy Linx Rule**: Automatically detects legacy URLs containing `-p12345` and redirects them to the `/superoferta` landing page.
- **Exact Slug Matching**: Extracts slugs from 404 URLs and strictly matches them to the live active slugs from the Google Shopping feed.
- **Fuzzy Text Matching**: Uses advanced string similarity algorithms (Levenshtein Distance) to find the closest active product when the URL structure has slightly changed, employing a strict `90%` similarity threshold to ensure high accuracy.
- **CSV Output Generation**: Exports the redirect mappings exactly conforming to the VTEX platform template format (`from;to;type;endDate`), ready for immediate import.

## How It Works

1. **Feed Ingestion**: The script downloads and parses the latest `googleshopping.xml` feed, extracting all active URLs and isolating product slugs.
2. **404 List Processing**: Reads a provided Excel/CSV file containing 404 errors (typically exported from Google Search Console or a crawling tool like Screaming Frog).
3. **Smart Matching Engine**: Applies the matching rules sequentially: Legacy Check -> Exact Match -> Fuzzy Match (≥ 90%).
4. **Export**: Generates the final CSV file for VTEX and a secondary detailed CSV for human review.

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

Run the primary matcher script:

```bash
python url_recovery.py
```

By default, the script looks for `googleshopping.xml` (configurable) and an input 404 Excel file. Ensure the input file exists in the directory or pass the correct filename to `process_404_list()`.

## Testing

This project uses `pytest` for robust unit testing to ensure matching logic reliability.

To run the test suite:
```bash
pytest tests/
```

## Continuous Integration

A GitHub Actions workflow is included (`.github/workflows/ci.yml`) which automatically runs the test suite on every `push` and `pull_request` to the `main` or `master` branches, ensuring code stability.

## Contribution & Trust

Built for VTEX store administrators and technical SEO specialists who need a reliable, data-driven approach to URL recovery. Contributions are welcome!
