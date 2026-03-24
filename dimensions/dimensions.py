#!/usr/bin/env python3
"""
Fetch height and width for IIIF images from a CSV file.

Expects a CSV with a "IIIF Access URL" column containing base IIIF image URLs
(no trailing parameters or /info.json). Writes "height" and "width" columns.

Usage:
    python dimensions.py input.csv
"""

import argparse
import concurrent.futures
import csv
import json
import os
import sys
import urllib.error
import urllib.request

SOURCE_COL = "IIIF Access URL"
HEIGHT_COL = "height"
WIDTH_COL = "width"


def get_output_directory():
    """Prompt user for output directory where the updated CSV will be saved."""
    default_dir = os.path.join(os.getcwd(), "output")
    raw = input(f"Output directory [press Enter for {default_dir}]: ").strip().strip("'\"")
    output_dir = raw if raw else default_dir
    os.makedirs(output_dir, exist_ok=True)
    print(f"Output will be saved to: {output_dir}\n")
    return output_dir


def fetch_dimensions(base_url: str) -> tuple[int | None, int | None]:
    """Fetch height and width from a IIIF info.json endpoint."""
    url = base_url.rstrip("/") + "/info.json"
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode())
            return data.get("height"), data.get("width")
    except urllib.error.HTTPError as e:
        print(f"  HTTP {e.code} for {url}", file=sys.stderr)
    except urllib.error.URLError as e:
        print(f"  URL error for {url}: {e.reason}", file=sys.stderr)
    except (json.JSONDecodeError, KeyError) as e:
        print(f"  Failed to parse info.json for {url}: {e}", file=sys.stderr)
    return None, None


def process_csv(input_path: str, output_path: str, max_workers: int = 20) -> None:
    with open(input_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if SOURCE_COL not in reader.fieldnames:
            sys.exit(f"Error: CSV has no '{SOURCE_COL}' column.")

        fieldnames = list(reader.fieldnames)
        if HEIGHT_COL not in fieldnames:
            fieldnames.append(HEIGHT_COL)
        if WIDTH_COL not in fieldnames:
            fieldnames.append(WIDTH_COL)

        rows = list(reader)

    total = len(rows)
    counts = {"total": total, "fetched": 0, "skipped_existing": 0, "skipped_no_url": 0, "failed": 0}

    # Pre-classify rows; report skips immediately
    for row in rows:
        base_url = row.get(SOURCE_COL, "").strip()
        if not base_url:
            row.setdefault(HEIGHT_COL, "")
            row.setdefault(WIDTH_COL, "")
            counts["skipped_no_url"] += 1
        elif row.get(HEIGHT_COL) and row.get(WIDTH_COL):
            counts["skipped_existing"] += 1

    to_fetch = {
        i: rows[i][SOURCE_COL].strip()
        for i in range(total)
        if rows[i].get(SOURCE_COL, "").strip()
        and not (rows[i].get(HEIGHT_COL) and rows[i].get(WIDTH_COL))
    }

    if counts["skipped_existing"]:
        print(f"Skipping {counts['skipped_existing']} rows that already have dimensions.")
    if counts["skipped_no_url"]:
        print(f"Skipping {counts['skipped_no_url']} rows with no IIIF Access URL.")

    n = len(to_fetch)
    if n:
        print(f"Fetching dimensions for {n} rows (up to {max_workers} in parallel)…")

    results: dict[int, tuple] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_idx = {executor.submit(fetch_dimensions, url): idx
                         for idx, url in to_fetch.items()}
        done = 0
        for future in concurrent.futures.as_completed(future_to_idx):
            done += 1
            idx = future_to_idx[future]
            results[idx] = future.result()
            h, w = results[idx]
            url = to_fetch[idx]
            if h is not None and w is not None:
                print(f"  [{done}/{n}] {w} × {h}  {url}")
            else:
                print(f"  [{done}/{n}] FAILED  {url}", file=sys.stderr)

    # Apply results in original row order
    for i, row in enumerate(rows):
        if i not in results:
            continue
        height, width = results[i]
        if height is not None and width is not None:
            row[HEIGHT_COL] = height
            row[WIDTH_COL] = width
            counts["fetched"] += 1
        else:
            row[HEIGHT_COL] = row.get(HEIGHT_COL, "")
            row[WIDTH_COL] = row.get(WIDTH_COL, "")
            counts["failed"] += 1

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nDone. Written to: {output_path}")
    print(f"Fetched: {counts['fetched']}  |  Already had dimensions: {counts['skipped_existing']}  "
          f"|  No URL: {counts['skipped_no_url']}  |  Failed: {counts['failed']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="dimensions",
        description="Fetch IIIF image dimensions (height and width) into a CSV.",
    )
    parser.add_argument("input", help="Path to input CSV file")
    args = parser.parse_args()

    output_dir = get_output_directory()
    output_path = os.path.join(output_dir, os.path.basename(args.input))
    process_csv(args.input, output_path)
