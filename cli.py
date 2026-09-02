import argparse
import logging
import os
import sys

from core.config import DEFAULT_XML_URL, RecoveryConfig
from core.pipeline import process_404_list


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Match 404 URLs to active product pages and generate VTEX redirects.")
    parser.add_argument("--input", default="404-gsc/Tabela.csv", help="Path to the 404 report (.csv or .xlsx).")
    parser.add_argument("--output-dir", default="output", help="Directory to write redirects.csv / redirects_review.csv into.")
    parser.add_argument("--xml-url", default=DEFAULT_XML_URL, help="Google Shopping XML feed URL.")
    parser.add_argument("--threshold", type=int, default=90, help="Minimum fuzzy match score (0-100) to accept a match.")
    parser.add_argument("--no-http-check", action="store_true", help="Skip verifying HTTP 200 status of destination URLs.")
    parser.add_argument("--max-workers", type=int, default=10, help="Concurrent threads for HTTP status checks.")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging.")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    if not os.path.exists(args.input):
        logging.error("Arquivo não encontrado: %s", args.input)
        return 1

    config = RecoveryConfig(
        xml_url=args.xml_url,
        threshold=args.threshold,
        check_http_status=not args.no_http_check,
        max_workers=args.max_workers,
    )

    output_file = os.path.join(args.output_dir, "redirects.csv")
    process_404_list(args.input, output_file, config=config)
    return 0


if __name__ == "__main__":
    sys.exit(main())
