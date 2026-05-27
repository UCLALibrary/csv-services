"""
Fetch height and width for IIIF images from a CSV file.

Expects a CSV with a "IIIF Access URL" column containing base IIIF image URLs
(no trailing parameters or /info.json). Writes "height" and "width" columns.
"""

import concurrent.futures
import csv
import io
import json
import threading
import urllib.error
import urllib.request

SOURCE_COL = "IIIF Access URL"
HEIGHT_COL = "media.height"
WIDTH_COL = "media.width"


def _fetch_dimensions(base_url: str) -> tuple[int | None, int | None]:
    """Fetch width and height from a IIIF info.json endpoint."""
    url = base_url.rstrip("/") + "/info.json"
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode())
            return data.get("height"), data.get("width")
    except (urllib.error.HTTPError, urllib.error.URLError, json.JSONDecodeError, KeyError):
        return None, None


def process_csv_content(
    csv_text: str,
    max_workers: int = 20,
    cancel: threading.Event | None = None,
) -> tuple[str, dict]:
    """
    Reads CSV text, fetches dimensions for any row with a IIIF Access URL
    that doesn't already have both height and width. Fetches are parallelized.

    Returns (updated_csv_text, counts_dict).
    counts_dict keys: total, fetched, skipped_existing, skipped_no_url, failed
    """
    reader = csv.DictReader(io.StringIO(csv_text))
    if reader.fieldnames is None or SOURCE_COL not in reader.fieldnames:
        raise ValueError(f"CSV has no '{SOURCE_COL}' column.")

    fieldnames = list(reader.fieldnames)
    if HEIGHT_COL not in fieldnames:
        fieldnames.append(HEIGHT_COL)
    if WIDTH_COL not in fieldnames:
        fieldnames.append(WIDTH_COL)

    rows = list(reader)
    counts = {"total": len(rows), "fetched": 0, "skipped_existing": 0, "skipped_no_url": 0, "failed": 0}

    # Pre-classify rows; only queue those that actually need a fetch
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
        for i in range(len(rows))
        if rows[i].get(SOURCE_COL, "").strip()
        and not (rows[i].get(HEIGHT_COL) and rows[i].get(WIDTH_COL))
    }

    # Parallel fetch — honour cancellation between completed futures
    results: dict[int, tuple] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_idx = {executor.submit(_fetch_dimensions, url): idx
                         for idx, url in to_fetch.items()}
        for future in concurrent.futures.as_completed(future_to_idx):
            if cancel and cancel.is_set():
                executor.shutdown(wait=False, cancel_futures=True)
                break
            results[future_to_idx[future]] = future.result()

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

    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue(), counts
