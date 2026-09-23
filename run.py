#!/usr/bin/env python3
"""CLI for Jev Token Scanner.

Usage:
    python run.py scan [--trending|--markets|--new] [--limit N] [--enrich]
    python run.py classify <token_id>
    python run.py watch [--interval N] [--trending|--markets]
    python run.py stats
"""

import argparse
import json
import os
import sys
import time
import yaml
from pathlib import Path
from dotenv import load_dotenv

from token_scanner import TokenScanner
from jev_client import JevClient
from classifier import TokenClassifier
from logger import ResultLogger


def load_config() -> dict:
    config_path = Path(__file__).parent / "config.yaml"
    with open(config_path) as f:
        return yaml.safe_load(f)


def setup():
    """Load config, env, and instantiate components."""
    load_dotenv()
    config = load_config()
    api_key = os.getenv("OPENROUTER_API_KEY")
    cg_key = os.getenv("COINGECKO_API_KEY")

    scanner = TokenScanner(config, api_key=cg_key)
    jev = JevClient(config, api_key=api_key)
    classifier = TokenClassifier(scanner, jev)
    logger = ResultLogger(config["scanner"]["log_file"])
    return config, scanner, jev, classifier, logger


def cmd_scan(args, config, scanner, classifier, logger):
    """Scan and classify tokens."""
    enrich = args.enrich

    if args.trending:
        print("Fetching trending tokens...")
        tokens = scanner.get_trending(limit=args.limit)
        scan_type = "trending"
    elif args.new:
        print("Fetching new listings...")
        tokens = scanner.get_new_listings(limit=args.limit)
        scan_type = "new"
    else:
        print("Fetching top market cap tokens...")
        tokens = scanner.get_markets(limit=args.limit)
        scan_type = "markets"

    print(f"Found {len(tokens)} tokens. Classifying...")
    results = classifier.classify_batch(tokens, enrich=enrich)
    logger.log_batch(results, scan_type=scan_type)

    for r in results:
        if "error" in r:
            print(f"  {r.get('symbol', '?'):>10}  ERROR: {r['error']}")
            continue
        cls = r.get("classification", {})
        quality = cls.get("project_quality", "?")
        score = cls.get("investment_score", "?")
        hp = "HP!" if cls.get("honeypot") else "   "
        rug = "RUG!" if cls.get("rugpull") else "    "
        print(f"  {r.get('symbol', '?'):>10}  quality={quality:<18} score={score:>3}  {hp} {rug}")

    print(f"\nDone. {len(results)} tokens classified. Results saved to {config['scanner']['log_file']}")


def cmd_classify(args, config, scanner, classifier, logger):
    """Classify a single token by ID."""
    print(f"Fetching data for '{args.token_id}'...")
    enriched = scanner.enrich_token(args.token_id)
    if not enriched:
        print(f"Token '{args.token_id}' not found on CoinGecko.")
        sys.exit(1)

    result = classifier.classify_token(enriched, enrich=False)
    logger.log(result, scan_type="single")
    print(json.dumps(result, indent=2, default=str))


def cmd_watch(args, config, scanner, classifier, logger):
    """Continuously scan and classify at intervals."""
    interval = args.interval or config["scanner"]["watch_interval"]
    print(f"Watch mode: scanning every {interval}s. Ctrl+C to stop.\n")

    while True:
        try:
            if args.trending:
                tokens = scanner.get_trending(limit=args.limit)
                scan_type = "watch-trending"
            else:
                tokens = scanner.get_markets(limit=args.limit)
                scan_type = "watch-markets"

            results = classifier.classify_batch(tokens, enrich=args.enrich)
            logger.log_batch(results, scan_type=scan_type)

            print(f"[{time.strftime('%H:%M:%S')}] Classified {len(results)} tokens")
            for r in results:
                cls = r.get("classification", {})
                print(f"  {r.get('symbol', '?'):>10}  quality={cls.get('project_quality', '?'):<18} score={cls.get('investment_score', '?')}")
            print()
        except KeyboardInterrupt:
            print("\nStopped.")
            break
        except Exception as e:
            print(f"Error: {e}")

        time.sleep(interval)


def cmd_stats(args, config, scanner, classifier, logger):
    """Show stats from logged results."""
    stats = logger.get_stats()
    print(json.dumps(stats, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Jev Token Scanner CLI")
    sub = parser.add_subparsers(dest="command")

    # scan
    p_scan = sub.add_parser("scan", help="Scan and classify tokens")
    p_scan.add_argument("--trending", action="store_true", help="Scan trending tokens")
    p_scan.add_argument("--markets", action="store_true", help="Scan by market cap (default)")
    p_scan.add_argument("--new", action="store_true", help="Scan new listings")
    p_scan.add_argument("--limit", type=int, default=20, help="Max tokens to scan")
    p_scan.add_argument("--enrich", action="store_true", help="Fetch detailed data per token")

    # classify
    p_cls = sub.add_parser("classify", help="Classify a single token by CoinGecko ID")
    p_cls.add_argument("token_id", help="CoinGecko token ID (e.g. 'bitcoin')")

    # watch
    p_watch = sub.add_parser("watch", help="Continuously scan at intervals")
    p_watch.add_argument("--interval", type=int, help="Seconds between scans")
    p_watch.add_argument("--trending", action="store_true", help="Watch trending tokens")
    p_watch.add_argument("--markets", action="store_true", default=True, help="Watch markets (default)")
    p_watch.add_argument("--limit", type=int, default=10, help="Tokens per scan")
    p_watch.add_argument("--enrich", action="store_true", help="Fetch detailed data")

    # stats
    sub.add_parser("stats", help="Show classification stats")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(0)

    config, scanner, jev, classifier, logger = setup()

    {"scan": cmd_scan, "classify": cmd_classify, "watch": cmd_watch, "stats": cmd_stats}[args.command](
        args, config, scanner, classifier, logger
    )


if __name__ == "__main__":
    main()
