import argparse
import csv
import os
import random
import uuid
import yaml
from getpass import getpass
import requests

def get_output_directory(file_prefix):
     """Prompt user for output directory, default to ./exports/{file_prefix}/ in current working directory."""
     default_output = os.path.join(os.getcwd(), "exports", file_prefix)

     print(f"\nDefault output directory: {default_output}")
     user_input = input("Enter output directory (or press Enter for default): ").strip()

     output_dir = user_input if user_input else default_output
     os.makedirs(output_dir, exist_ok=True)
     print(f"CSVs will be saved to: {output_dir}\n")
     return output_dir

YAML_TEMPLATE = """
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

ALL_HEADERS = [
    "Item ARK",
    "Parent ARK",
    "Object Type",
    "Title",
    "File Name",
]

COLLECTION_HEADERS = [
    "Visibility",
    "Genre",
    "Repository",
    "Date.creation",
    "Date.normalized",
    "Type.typeOfResource",
    "Rights.copyrightStatus",
    "Rights.servicesContact",
    "Language"
]

WORK_HEADERS = [
    "viewingHint",
    "Text direction"
]

SEQUENCE_HEADERS = ["Item Sequence"]


# Function to mint an ARK using the ERC profile
def mint_ark(username, password, shoulder):
    url = f'https://ezid.cdlib.org/shoulder/{shoulder}'
    headers = {
        'Content-Type': 'text/plain; charset=UTF-8',
    }
    data = {
        '_profile': 'erc',
    }

    data_encoded = '\n'.join(f'{k}: {v}' for k, v in data.items()).encode('utf-8')

    print(f"Request URL: {url}")
    print(f"Request Headers: {headers}")
    print(f"Request Data: {data}")

    response = requests.post(url, headers=headers, data=data_encoded, auth=(username, password))

    if response.status_code == 201:
        ark = response.text.strip()
        if ark.startswith("success: "):
            return ark[len("success: "):].strip()
        return ark
    else:
        print(f"Error minting ARK: {response.status_code} - {response.text}")
        print(f"Data sent: {data}")
        return None


# Betanumeric alphabet (no vowels) used by the NOID standard
_NOID_CHARS = '0123456789bcdfghjkmnpqrstvwxz'

def child_ark(parent_ark):
    """Derive a child ARK by appending a locally-generated NOID qualifier to the parent ARK."""
    noid = ''.join(random.choices(_NOID_CHARS, k=8))
    return f"{parent_ark}/{noid}"


def fake_ark():
    """Generate a placeholder ARK for testing when EZID credentials are not provided."""
    return f"ark:/FAKE/{uuid.uuid4().hex[:8]}"


def get_ark(username, password, shoulder):
    """Mint a real ARK if credentials are provided, otherwise generate a placeholder."""
    if username and password and shoulder:
        ark = mint_ark(username, password, shoulder)
        return ark if ark else "ERROR: ARK not minted"
    else:
        ark = fake_ark()
        print(f"No EZID credentials provided — using placeholder ARK: {ark}")
        return ark


def check_inputs(path):
    yaml_path = os.path.join(path, "inputs.yml")
    if os.path.exists(yaml_path):
        return True
    print(f"Input file not found. Creating template {yaml_path}.")
    with open(yaml_path, "w") as yaml_file:
        yaml_file.write(YAML_TEMPLATE)
    return False


def get_inputs(path):
    yaml_path = os.path.join(path, "inputs.yml")
    with open(yaml_path, "r") as yaml_file:
        defaults = yaml.load(yaml_file, Loader=yaml.Loader)
        title = defaults.pop("Collection Title")
        shortcode = defaults.pop("Collection Shortcode", None)
        file_prefix = shortcode if shortcode else title
        collection_ark = defaults.pop("Collection ARK")
        page_prefix = defaults.pop("page title prefix")
        extensions_raw = defaults.pop("file extensions")
        if extensions_raw:
            file_extensions = tuple(ext.strip() for ext in str(extensions_raw).split(","))
        else:
            file_extensions = None
        work_defaults = {k: defaults.pop(k) for k in WORK_HEADERS}
        ezid_user = defaults.pop("EZID Username")
        ezid_password = defaults.pop("EZID Password")
        ark_shoulder = defaults.pop("ARK Shoulder")
        return title, file_prefix, collection_ark, defaults, work_defaults, page_prefix, file_extensions, ezid_user, ezid_password, ark_shoulder


def process_level0(root, title, file_prefix, ark, defaults, ezid_user, ezid_password, ark_shoulder, output_dir):
    if ark:
        print(f"Collection ARK provided ({ark}) — skipping collection CSV.")
        return ark
    ark = get_ark(ezid_user, ezid_password, ark_shoulder)
    csv_path = os.path.join(output_dir, f"{file_prefix}-collection.csv")
    data = {
        "Item ARK": ark,
        "Object Type": "Collection",
        "Title": title
    }
    data.update(defaults)
    headers = ALL_HEADERS + COLLECTION_HEADERS
    with open(csv_path, "w") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=headers)
        writer.writeheader()
        writer.writerow(data)
    return ark


def detect_mode(root, file_extensions):
    """
    Auto-detect collection structure:
      'all_simple'  — image files directly at collection root (no subfolders)
      'all_complex' — work subfolders directly at collection root
      'mixed'       — a 'simple/' folder and/or 'complex/' folder at collection root
    """
    dir_names = {d.name for d in os.scandir(root) if d.is_dir()}

    if 'simple' in dir_names or 'complex' in dir_names:
        return 'mixed'

    image_files = [
        f for f in os.scandir(root)
        if f.is_file() and (
            not file_extensions or os.path.splitext(f.name)[1].lower() in file_extensions
        )
    ]
    return 'all_simple' if image_files else 'all_complex'


def _image_files(path, file_extensions):
    """Return sorted list of image file entries in path, filtered by extension."""
    all_files = sorted([f for f in os.scandir(path) if f.is_file()], key=lambda x: x.name)
    if file_extensions:
        return [f for f in all_files if os.path.splitext(f.name)[1].lower() in file_extensions]
    return all_files


def _write_simple_work_row(file_entry, collection_ark, defaults, work_defaults, writer, ezid_user, ezid_password, ark_shoulder):
    """Write a single Work row for a simple item (one image = one Work, File Name included)."""
    title, _ = os.path.splitext(file_entry.name)
    ark = get_ark(ezid_user, ezid_password, ark_shoulder)
    data = {
        "Item ARK": ark,
        "Parent ARK": collection_ark,
        "Object Type": "Work",
        "Title": title,
        "File Name": file_entry.path,
    }
    data.update(defaults)
    data.update(work_defaults)
    writer.writerow(data)


def _write_complex_work_row(dir_entry, collection_ark, defaults, work_defaults, writer, ezid_user, ezid_password, ark_shoulder):
    """Write a single Work row for a complex item (folder of pages). Returns the minted ARK."""
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


def process_works_and_pages(root, title, file_prefix, collection_ark, defaults, work_defaults, page_prefix, file_extensions, mode, ezid_user, ezid_password, ark_shoulder, output_dir):
    works_headers = ALL_HEADERS + COLLECTION_HEADERS + WORK_HEADERS
    complex_works = []  # (dir_entry, work_ark) pairs that need page rows

    if mode == 'all_simple':
        print("Mode: all simple — image files at collection root → Works only.")
        works_csv_path = os.path.join(output_dir, f"{file_prefix}-works.csv")
        with open(works_csv_path, "w") as works_file:
            writer = csv.DictWriter(works_file, fieldnames=works_headers)
            writer.writeheader()
            for f in _image_files(root, file_extensions):
                _write_simple_work_row(f, collection_ark, defaults, work_defaults,
                                       writer, ezid_user, ezid_password, ark_shoulder)

    elif mode == 'all_complex':
        print("Mode: all complex — subfolders at collection root → Works + Pages.")
        works_csv_path = os.path.join(output_dir, f"{file_prefix}-works.csv")
        with open(works_csv_path, "w") as works_file:
            writer = csv.DictWriter(works_file, fieldnames=works_headers)
            writer.writeheader()
            dirs = sorted([d for d in os.scandir(root) if d.is_dir()], key=lambda x: x.name)
            for d in dirs:
                work_ark = _write_complex_work_row(d, collection_ark, defaults, work_defaults,
                                                   writer, ezid_user, ezid_password, ark_shoulder)
                complex_works.append((d, work_ark))

    elif mode == 'mixed':
        print("Mode: mixed — 'simple/' folder → works-simple.csv; 'complex/' folder → works-complex.csv + pages.")
        simple_path = os.path.join(root, 'simple')
        complex_path = os.path.join(root, 'complex')

        if os.path.isdir(simple_path):
            simple_csv_path = os.path.join(output_dir, f"{file_prefix}-works-simple.csv")
            with open(simple_csv_path, "w") as simple_file:
                writer = csv.DictWriter(simple_file, fieldnames=works_headers)
                writer.writeheader()
                for f in _image_files(simple_path, file_extensions):
                    _write_simple_work_row(f, collection_ark, defaults, work_defaults,
                                           writer, ezid_user, ezid_password, ark_shoulder)

        if os.path.isdir(complex_path):
            complex_csv_path = os.path.join(output_dir, f"{file_prefix}-works-complex.csv")
            with open(complex_csv_path, "w") as complex_file:
                writer = csv.DictWriter(complex_file, fieldnames=works_headers)
                writer.writeheader()
                dirs = sorted([d for d in os.scandir(complex_path) if d.is_dir()], key=lambda x: x.name)
                for d in dirs:
                    work_ark = _write_complex_work_row(d, collection_ark, defaults, work_defaults,
                                                       writer, ezid_user, ezid_password, ark_shoulder)
                    complex_works.append((d, work_ark))

    # Write pages CSV only if there are complex works
    if complex_works:
        pages_csv_path = os.path.join(output_dir, f"{file_prefix}-pages.csv")
        pages_headers = ALL_HEADERS + SEQUENCE_HEADERS
        with open(pages_csv_path, "w") as pages_file:
            pages_writer = csv.DictWriter(pages_file, fieldnames=pages_headers)
            pages_writer.writeheader()
            for work_dir, work_ark in complex_works:
                for seq, f in enumerate(_image_files(work_dir.path, file_extensions), start=1):
                    name_without_ext, _ = os.path.splitext(f.name)
                    page_title = f"{page_prefix} {seq}" if page_prefix else name_without_ext
                    data = {
                        "Item ARK": child_ark(work_ark),
                        "Parent ARK": work_ark,
                        "Object Type": "Page",
                        "Title": page_title,
                        "File Name": f.path,
                        "Item Sequence": seq
                    }
                    pages_writer.writerow(data)


def main(root):
    title, file_prefix, collection_ark, defaults, work_defaults, page_prefix, file_extensions, ezid_user, ezid_password, ark_shoulder = get_inputs(root)
    output_dir = get_output_directory(file_prefix)
    collection_ark = process_level0(root, title, file_prefix, collection_ark, defaults, ezid_user, ezid_password, ark_shoulder, output_dir)
    mode = detect_mode(root, file_extensions)
    process_works_and_pages(root, title, file_prefix, collection_ark, defaults, work_defaults, page_prefix,
                             file_extensions, mode, ezid_user, ezid_password, ark_shoulder, output_dir)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog='standard',
        description=(
            'Generates CSVs for standard collections. Auto-detects structure: '
            'all-simple (images at root), all-complex (work subfolders), '
            'or mixed (simple/ and complex/ folders at root).'
        )
    )
    parser.add_argument('path', help='the path to the collection')
    args = parser.parse_args()
    if check_inputs(args.path) is True:
        main(args.path)
