import csv
import io
import os

from .ark import get_ark, child_ark

ALL_HEADERS = ["Item ARK", "Parent ARK", "Object Type", "Title", "File Name"]

COLLECTION_HEADERS = [
    "Visibility", "Genre", "Repository", "Date.creation", "Date.normalized",
    "Type.typeOfResource", "Rights.copyrightStatus", "Rights.servicesContact", "Language"
]

WORK_HEADERS = ["viewingHint", "Text direction"]

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

# Work Display Defaults
viewingHint:
Text direction:

# Page Defaults (complex works only)
page title prefix:
# Comma-separated list of file extensions to include (e.g. .tif,.jpg)
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
    extensions_raw = c.pop("file extensions", None)
    if extensions_raw:
        file_extensions = tuple(ext.strip() for ext in str(extensions_raw).split(","))
    else:
        file_extensions = None
    ezid_user = c.pop("EZID Username", None)
    ezid_password = c.pop("EZID Password", None)
    ark_shoulder = c.pop("ARK Shoulder", None)
    work_defaults = {k: c.pop(k, None) for k in WORK_HEADERS}
    defaults = {k: c.get(k) for k in COLLECTION_HEADERS if k in c}
    return title, file_prefix, collection_ark, defaults, work_defaults, page_prefix, file_extensions, ezid_user, ezid_password, ark_shoulder


def _image_files(path, file_extensions):
    """Return sorted list of file entries in path, optionally filtered by extension."""
    all_files = sorted([f for f in os.scandir(path) if f.is_file()], key=lambda x: x.name)
    if file_extensions:
        return [f for f in all_files if os.path.splitext(f.name)[1].lower() in file_extensions]
    return all_files


def detect_mode(scan_path, file_extensions):
    """
    Auto-detect collection structure:
      'all_simple'  — image files directly at collection root
      'all_complex' — work subfolders at collection root
      'mixed'       — 'simple/' and/or 'complex/' folders at collection root
    """
    dir_names = {d.name for d in os.scandir(scan_path) if d.is_dir()}
    if 'simple' in dir_names or 'complex' in dir_names:
        return 'mixed'
    image_files = [
        f for f in os.scandir(scan_path)
        if f.is_file() and (
            not file_extensions or os.path.splitext(f.name)[1].lower() in file_extensions
        )
    ]
    return 'all_simple' if image_files else 'all_complex'


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


def _write_simple_work_row(file_entry, scan_path, base_path, collection_ark, defaults, work_defaults, writer, ezid_user, ezid_password, ark_shoulder):
    title, _ = os.path.splitext(file_entry.name)
    ark = get_ark(ezid_user, ezid_password, ark_shoulder)
    data = {
        "Item ARK": ark,
        "Parent ARK": collection_ark,
        "Object Type": "Work",
        "Title": title,
        "File Name": _real_path(file_entry.path, scan_path, base_path),
    }
    data.update(defaults)
    data.update(work_defaults)
    writer.writerow(data)


def _write_complex_work_row(dir_entry, collection_ark, defaults, work_defaults, writer, ezid_user, ezid_password, ark_shoulder):
    ark = get_ark(ezid_user, ezid_password, ark_shoulder)
    data = {
        "Item ARK": ark,
        "Parent ARK": collection_ark,
        "Object Type": "Work",
        "Title": dir_entry.name,
    }
    data.update(defaults)
    data.update(work_defaults)
    writer.writerow(data)
    return ark


def _process_works_and_pages(scan_path, base_path, file_prefix, collection_ark, defaults, work_defaults, page_prefix, file_extensions, mode, ezid_user, ezid_password, ark_shoulder):
    works_headers = ALL_HEADERS + COLLECTION_HEADERS + WORK_HEADERS
    complex_works = []
    outputs = {}

    if mode == 'all_simple':
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=works_headers, extrasaction='ignore')
        writer.writeheader()
        for f in _image_files(scan_path, file_extensions):
            _write_simple_work_row(f, scan_path, base_path, collection_ark, defaults, work_defaults, writer, ezid_user, ezid_password, ark_shoulder)
        outputs[f"{file_prefix}-works.csv"] = buf.getvalue()

    elif mode == 'all_complex':
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=works_headers, extrasaction='ignore')
        writer.writeheader()
        dirs = sorted([d for d in os.scandir(scan_path) if d.is_dir()], key=lambda x: x.name)
        for d in dirs:
            work_ark = _write_complex_work_row(d, collection_ark, defaults, work_defaults, writer, ezid_user, ezid_password, ark_shoulder)
            complex_works.append((d, work_ark))
        outputs[f"{file_prefix}-works.csv"] = buf.getvalue()

    elif mode == 'mixed':
        simple_path = os.path.join(scan_path, 'simple')
        complex_path = os.path.join(scan_path, 'complex')

        if os.path.isdir(simple_path):
            buf = io.StringIO()
            writer = csv.DictWriter(buf, fieldnames=works_headers, extrasaction='ignore')
            writer.writeheader()
            for f in _image_files(simple_path, file_extensions):
                _write_simple_work_row(f, scan_path, base_path, collection_ark, defaults, work_defaults, writer, ezid_user, ezid_password, ark_shoulder)
            outputs[f"{file_prefix}-works-simple.csv"] = buf.getvalue()

        if os.path.isdir(complex_path):
            buf = io.StringIO()
            writer = csv.DictWriter(buf, fieldnames=works_headers, extrasaction='ignore')
            writer.writeheader()
            dirs = sorted([d for d in os.scandir(complex_path) if d.is_dir()], key=lambda x: x.name)
            for d in dirs:
                work_ark = _write_complex_work_row(d, collection_ark, defaults, work_defaults, writer, ezid_user, ezid_password, ark_shoulder)
                complex_works.append((d, work_ark))
            outputs[f"{file_prefix}-works-complex.csv"] = buf.getvalue()

    if complex_works:
        buf = io.StringIO()
        pages_headers = ALL_HEADERS + SEQUENCE_HEADERS
        writer = csv.DictWriter(buf, fieldnames=pages_headers, extrasaction='ignore')
        writer.writeheader()
        for work_dir, work_ark in complex_works:
            for seq, f in enumerate(_image_files(work_dir.path, file_extensions), start=1):
                name_without_ext, _ = os.path.splitext(f.name)
                page_title = f"{page_prefix} {seq}".strip() if page_prefix else name_without_ext
                data = {
                    "Item ARK": child_ark(work_ark),
                    "Parent ARK": work_ark,
                    "Object Type": "Page",
                    "Title": page_title,
                    "File Name": _real_path(f.path, scan_path, base_path),
                    "Item Sequence": seq
                }
                writer.writerow(data)
        outputs[f"{file_prefix}-pages.csv"] = buf.getvalue()

    return outputs


def run(scan_path, base_path, config):
    """
    Generate standard collection CSVs. Auto-detects structure (all_simple,
    all_complex, or mixed).

    Args:
        scan_path: Path to walk for directory structure. In CLI use, this is the
                   collection directory. In web use, this may be a temp scaffold dir.
        base_path: Root path to use in File Name column — always the user's real
                   collection path.
        config:    Dict with keys matching the inputs.yml template fields.

    Returns:
        Dict mapping CSV filename to CSV content as a string.
    """
    title, file_prefix, collection_ark, defaults, work_defaults, page_prefix, file_extensions, ezid_user, ezid_password, ark_shoulder = _parse_config(config)

    outputs = {}
    collection_ark, coll_csv = _process_level0(title, file_prefix, collection_ark, defaults, ezid_user, ezid_password, ark_shoulder)
    outputs.update(coll_csv)

    mode = detect_mode(scan_path, file_extensions)
    outputs.update(_process_works_and_pages(scan_path, base_path, file_prefix, collection_ark, defaults, work_defaults, page_prefix, file_extensions, mode, ezid_user, ezid_password, ark_shoulder))

    return outputs
