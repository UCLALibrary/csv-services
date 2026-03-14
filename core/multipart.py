import csv
import io
import os

from .ark import get_ark, child_ark

ALL_HEADERS = ["Item ARK", "Parent ARK", "Object Type", "Title", "File Name"]

COLLECTION_HEADERS = [
    "Visibility", "Genre", "Repository", "Date.creation", "Date.normalized",
    "Type.typeOfResource", "Rights.copyrightStatus", "Rights.servicesContact", "Language"
]

MULTI_HEADERS = COLLECTION_HEADERS + ["IIIF Object Type", "viewingHint"]

VOL_HEADERS = ["viewingHint", "Text direction"]

PAGE_HEADERS = ["Item Sequence"]

YAML_TEMPLATE = """\
Collection Title:
Collection Shortcode:
Collection ARK:

# Collection and Multipart Defaults
Visibility:
Genre:
Repository:
Date.creation:
Date.normalized:
Type.typeOfResource:
Rights.copyrightStatus:
Rights.servicesContact:
Language:

# Volume Defaults
viewingHint:
Text direction:
vol title prefix:
page title prefix:
EZID Username:
EZID Password:
ARK Shoulder:
"""


def _real_path(entry_path, scan_path, base_path):
    """Convert a scanned path to the user's real path for File Name column."""
    if scan_path == base_path:
        return entry_path
    return os.path.join(base_path, os.path.relpath(entry_path, scan_path))


def _parse_config(config):
    c = dict(config)
    title = c.pop("Collection Title", None)
    shortcode = c.pop("Collection Shortcode", None)
    file_prefix = shortcode or title or "output"
    collection_ark = c.pop("Collection ARK", None)
    vol_prefix = c.pop("vol title prefix", None) or ""
    page_prefix = c.pop("page title prefix", None) or ""
    ezid_user = c.pop("EZID Username", None)
    ezid_password = c.pop("EZID Password", None)
    ark_shoulder = c.pop("ARK Shoulder", None)
    vol_defaults = {k: c.pop(k, None) for k in VOL_HEADERS}
    defaults = {k: c.get(k) for k in COLLECTION_HEADERS if k in c}
    return title, file_prefix, collection_ark, defaults, vol_prefix, page_prefix, vol_defaults, ezid_user, ezid_password, ark_shoulder


def _process_level0(title, file_prefix, ark, defaults, ezid_user, ezid_password, ark_shoulder):
    if ark:
        return ark, {}
    ark = get_ark(ezid_user, ezid_password, ark_shoulder)
    buf = io.StringIO()
    headers = ALL_HEADERS + COLLECTION_HEADERS
    writer = csv.DictWriter(buf, fieldnames=headers, extrasaction='ignore')
    writer.writeheader()
    data = {"Item ARK": ark, "Object Type": "Collection", "Title": title}
    data.update(defaults)
    writer.writerow(data)
    return ark, {f"{file_prefix}-collection.csv": buf.getvalue()}


def _process_level1(scan_path, base_path, title, file_prefix, collection_ark, defaults, ezid_user, ezid_password, ark_shoulder):
    dirs = sorted([d for d in os.scandir(scan_path) if d.is_dir()], key=lambda x: x.name)
    buf = io.StringIO()
    headers = ALL_HEADERS + MULTI_HEADERS
    writer = csv.DictWriter(buf, fieldnames=headers, extrasaction='ignore')
    writer.writeheader()
    works = []
    for d in dirs:
        ark = get_ark(ezid_user, ezid_password, ark_shoulder)
        data = {
            "Item ARK": ark,
            "Parent ARK": collection_ark,
            "IIIF Object Type": "Collection",
            "Object Type": "Work",
            "viewingHint": "multi-part",
            "Title": d.name
        }
        data.update(defaults)
        writer.writerow(data)
        works.append((d, ark))
    return works, {f"{file_prefix}-multiworks.csv": buf.getvalue()}


def _process_level2(scan_path, base_path, file_prefix, works, vol_prefix, vol_defaults, ezid_user, ezid_password, ark_shoulder):
    buf = io.StringIO()
    headers = ALL_HEADERS + VOL_HEADERS
    writer = csv.DictWriter(buf, fieldnames=headers, extrasaction='ignore')
    writer.writeheader()
    volumes = []
    for work, work_ark in works:
        dirs = sorted([d for d in os.scandir(work.path) if d.is_dir()], key=lambda x: x.name)
        for d in dirs:
            ark = get_ark(ezid_user, ezid_password, ark_shoulder)
            data = {
                "Item ARK": ark,
                "Parent ARK": work_ark,
                "Object Type": "Work",
                "Title": f"{vol_prefix} {d.name}".strip()
            }
            data.update(vol_defaults)
            writer.writerow(data)
            volumes.append((d, ark))
    return volumes, {f"{file_prefix}-vols.csv": buf.getvalue()}


def _process_level3(scan_path, base_path, file_prefix, volumes, page_prefix):
    buf = io.StringIO()
    headers = ALL_HEADERS + PAGE_HEADERS
    writer = csv.DictWriter(buf, fieldnames=headers, extrasaction='ignore')
    writer.writeheader()
    for vol, vol_ark in volumes:
        files = sorted([f.name for f in os.scandir(vol.path) if f.is_file()])
        for seq, file in enumerate(files, start=1):
            ark = child_ark(vol_ark)
            data = {
                "Item ARK": ark,
                "Parent ARK": vol_ark,
                "Object Type": "Page",
                "Title": f"{page_prefix} {seq}".strip(),
                "File Name": _real_path(os.path.join(vol.path, file), scan_path, base_path),
                "Item Sequence": seq
            }
            writer.writerow(data)
    return {f"{file_prefix}-pages.csv": buf.getvalue()}


def run(scan_path, base_path, config):
    """
    Generate multipart collection CSVs.

    Args:
        scan_path: Path to walk for directory structure. In CLI use, this is the
                   collection directory. In web use, this may be a temp scaffold dir.
        base_path: Root path to use in File Name column — always the user's real
                   collection path.
        config:    Dict with keys matching the inputs.yml template fields.

    Returns:
        Dict mapping CSV filename to CSV content as a string.
    """
    title, file_prefix, collection_ark, defaults, vol_prefix, page_prefix, vol_defaults, ezid_user, ezid_password, ark_shoulder = _parse_config(config)

    outputs = {}
    collection_ark, coll_csv = _process_level0(title, file_prefix, collection_ark, defaults, ezid_user, ezid_password, ark_shoulder)
    outputs.update(coll_csv)

    works, works_csv = _process_level1(scan_path, base_path, title, file_prefix, collection_ark, defaults, ezid_user, ezid_password, ark_shoulder)
    outputs.update(works_csv)

    volumes, vols_csv = _process_level2(scan_path, base_path, file_prefix, works, vol_prefix, vol_defaults, ezid_user, ezid_password, ark_shoulder)
    outputs.update(vols_csv)

    outputs.update(_process_level3(scan_path, base_path, file_prefix, volumes, page_prefix))

    return outputs
