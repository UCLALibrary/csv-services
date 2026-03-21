# Digital Collections CSV Services

Tools for generating CSVs for digital collections ingest. Available as a hosted web app or as local command-line scripts.

---

## Option 1: Web App

Use the hosted app at **https://digital-collections-csv-services.onrender.com/**

### Collection Types

#### Standard
Auto-detects the folder structure of your collection:

- **Simple** — Image files are directly inside the collection root (one level deep)
- **Complex** — Work subfolders are inside the collection root, each containing image files
- **Mixed** — Both simple and complex works in the same collection; expects folders named `simple` and `complex` at the collection or batch root

#### Multipart
Four-level hierarchy for multipart works:

```
collection/
  work1/
    vol1/
      page001.tif
      page002.tif
    vol2/
      ...
  work2/
    ...
```

#### Layers
For IIIF Choice/Layers — four-level hierarchy:

```
collection/
  work1/
    page1/
      layer1.tif
      layer2.tif
    page2/
      ...
  work2/
    ...
```

---

## Option 2: Local Scripts

### Installation

```
git clone git@github.com:UCLALibrary/multipart.git
cd multipart
python -m venv ENV
source ENV/bin/activate
pip install -r requirements.txt
```

### Usage

1. Run the script for your collection type, passing the path to the collection folder:

    ```
    python standard/standard.py path/to/collection
    python multipart/multipart.py path/to/collection
    python layers/layers.py path/to/collection
    ```

2. The script will prompt for an output directory where `inputs.yml` and the generated CSVs will be saved.

3. On the first run, an `inputs.yml` template is written to the output directory. Open it and fill in the collection metadata and any EZID credentials for ARK minting.

    ```
    vim path/to/output/inputs.yml
    ```

4. Run the script again. It will use the values from `inputs.yml` to generate the CSVs.
