import csv
import io
import os

from .ark import get_ark, child_ark

ALL_HEADERS = ["Item ARK", "Parent ARK", "Object Type", "Title", "File Name"]

COLLECTION_HEADERS = [
    "Visibility", "Genre", "Repository", "Date.creation", "Date.normalized",
    "Type.typeOfResource", "Rights.copyrightStatus", "Rights.servicesContact", "Language"
]

PAGE_VOL_HEADERS = ["viewingHint", "Text direction"]

SEQUENCE_HEADERS = ["Item Sequence"]

YAML_TEMPLATE = """\
Collection Title:
Collection Shortcode:
Collection ARK:

# Collection and Work Defaults
Visibility:
Genre:
Repository:
Date.creation:
Date.normalized:
Type.typeOfResource:
Rights.copyrightStatus:
Rights.servicesContact:
Language:

# Page Defaults
viewingHint:
Text direction:
page title prefix:

# Layer/Choice Defaults
# Set Layer Type to "Choice" or "Layer"
Layer Type: Choice
layer title prefix:
# Comma-separated list of file extensions to include as layers (e.g. .tif,.jpg)
# Leave blank to include all files
file extensions: .tif

# ARK Minting Credentials
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
    page_prefix = c.pop("page title prefix", None) or ""
    layer_prefix = c.pop("layer title prefix", None) or ""
    layer_type = c.pop("Layer Type", "Choice")
    extensions_raw = c.pop("file extensions", None)
    if extensions_raw:
        file_extensions = tuple(ext.strip() for ext in str(extensions_raw).split(","))
    else:
        file_extensions = None
    ezid_user = c.pop("EZID Username", None)
    ezid_password = c.pop("EZID Password", None)
    ark_shoulder = c.pop("ARK Shoulder", None)
    page_vol_defaults = {k: c.pop(k, None) for k in PAGE_VOL_HEADERS}
    defaults = {k: c.get(k) for k in COLLECTION_HEADERS if k in c}
    return title, file_prefix, collection_ark, defaults, page_prefix, layer_prefix, layer_type, file_extensions, page_vol_defaults, ezid_user, ezid_password, ark_shoulder


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


def _process_level1(scan_path, file_prefix, collection_ark, defaults, page_vol_defaults, ezid_user, ezid_password, ark_shoulder):
    dirs = sorted([d for d in os.scandir(scan_path) if d.is_dir()], key=lambda x: x.name)
    buf = io.StringIO()
    headers = ALL_HEADERS + COLLECTION_HEADERS + PAGE_VOL_HEADERS
    writer = csv.DictWriter(buf, fieldnames=headers, extrasaction='ignore')
    writer.writeheader()
    works = []
    for d in dirs:
        ark = get_ark(ezid_user, ezid_password, ark_shoulder)
        data = {
            "Item ARK": ark,
            "Parent ARK": collection_ark,
            "Object Type": "Work",
            "Title": d.name
        }
        data.update(defaults)
        data.update(page_vol_defaults)
        writer.writerow(data)
        works.append((d, ark))
    return works, {f"{file_prefix}-works.csv": buf.getvalue()}


def _process_level2(file_prefix, works, page_prefix, ezid_user, ezid_password, ark_shoulder):
    buf = io.StringIO()
    headers = ALL_HEADERS + SEQUENCE_HEADERS
    writer = csv.DictWriter(buf, fieldnames=headers, extrasaction='ignore')
    writer.writeheader()
    pages = []
    for work, work_ark in works:
        dirs = sorted([d for d in os.scandir(work.path) if d.is_dir()], key=lambda x: x.name)
        for seq, d in enumerate(dirs, start=1):
            ark = get_ark(ezid_user, ezid_password, ark_shoulder)
            page_title = f"{page_prefix} {seq}".strip() if page_prefix else d.name
            data = {
                "Item ARK": ark,
                "Parent ARK": work_ark,
                "Object Type": "Page",
                "Title": page_title,
                "Item Sequence": seq
            }
            writer.writerow(data)
            pages.append((d, ark))
    return pages, {f"{file_prefix}-pages.csv": buf.getvalue()}


def _process_level3(scan_path, base_path, file_prefix, pages, layer_type, layer_prefix, file_extensions):
    buf = io.StringIO()
    headers = ALL_HEADERS + SEQUENCE_HEADERS
    writer = csv.DictWriter(buf, fieldnames=headers, extrasaction='ignore')
    writer.writeheader()
    for page_dir, page_ark in pages:
        all_files = sorted([f.name for f in os.scandir(page_dir.path) if f.is_file()])
        if file_extensions:
            files = [f for f in all_files if os.path.splitext(f)[1].lower() in file_extensions]
        else:
            files = all_files
        for seq, file in enumerate(files, start=1):
            ark = child_ark(page_ark)
            layer_title = f"{layer_prefix} {seq}".strip() if layer_prefix else page_dir.name
            data = {
                "Item ARK": ark,
                "Parent ARK": page_ark,
                "Object Type": layer_type,
                "Title": layer_title,
                "File Name": _real_path(os.path.join(page_dir.path, file), scan_path, base_path),
                "Item Sequence": seq
            }
            writer.writerow(data)
    return {f"{file_prefix}-layers.csv": buf.getvalue()}


def run(scan_path, base_path, config):
    """
    Generate layers/choice collection CSVs.

    Args:
        scan_path: Path to walk for directory structure. In CLI use, this is the
                   collection directory. In web use, this may be a temp scaffold dir.
        base_path: Root path to use in File Name column — always the user's real
                   collection path.
        config:    Dict with keys matching the inputs.yml template fields.

    Returns:
        Dict mapping CSV filename to CSV content as a string.
    """
    title, file_prefix, collection_ark, defaults, page_prefix, layer_prefix, layer_type, file_extensions, page_vol_defaults, ezid_user, ezid_password, ark_shoulder = _parse_config(config)

    outputs = {}
    collection_ark, coll_csv = _process_level0(title, file_prefix, collection_ark, defaults, ezid_user, ezid_password, ark_shoulder)
    outputs.update(coll_csv)

    works, works_csv = _process_level1(scan_path, file_prefix, collection_ark, defaults, page_vol_defaults, ezid_user, ezid_password, ark_shoulder)
    outputs.update(works_csv)

    pages, pages_csv = _process_level2(file_prefix, works, page_prefix, ezid_user, ezid_password, ark_shoulder)
    outputs.update(pages_csv)

    outputs.update(_process_level3(scan_path, base_path, file_prefix, pages, layer_type, layer_prefix, file_extensions))

    return outputs
