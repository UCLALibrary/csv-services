# Digital Collections CSV Services

Scripts for generating CSVs for digital collections processing and ingest.

> A hosted web app is also available at **https://digital-collections-csv-services.onrender.com/** — see the [webapp README](https://github.com/UCLALibrary/csv-services/blob/webapp/README.md) for more information.

## Installation

```
git clone git@github.com:UCLALibrary/csv-services.git
cd csv-services
python -m venv ENV
source ENV/bin/activate
pip install -r requirements.txt
```

## Usage

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

## inputs.yml

The `inputs.yml` template is generated automatically on the first run. It has the following sections:

**Collection**
- `Collection Title` — display title for the collection
- `Collection Shortcode` — short identifier used as the CSV filename prefix
- `Collection ARK` — leave blank to generate a new ARK; if the collection already exists, enter its ARK here and no collection CSV will be generated

**Collection and Work Defaults** — metadata applied to all works in the collection:
`Visibility`, `Genre`, `Repository`, `Date.creation`, `Date.normalized`, `Type.typeOfResource`, `Rights.copyrightStatus`, `Rights.servicesContact`, `Language`

**Work Display Defaults**
- `viewingHint` — e.g. `paged` or `continuous`
- `Text direction`

**Page Defaults**
- `page title prefix` — e.g. `Page` (produces "Page 1", "Page 2", …)
- `file extensions` — comma-separated list of extensions to include (e.g. `.tif,.jpg`); leave blank to include all files

**ARK Minting Credentials**
- `EZID Username`, `EZID Password`, `ARK Shoulder` — see below

## ARK Minting

EZID credentials are optional. Without them, the scripts generate placeholder ARKs in the format `ark:/FAKE/...`, which is useful for testing and reviewing the CSV structure before a real ingest run.

When credentials are provided, the script mints a real ARK via EZID for each Collection, Multipart Work, Work, and Page (when there are Layers). ARKs for rows that carry an image file path — Object Types "Page" in Standard and Multipart, and "Layer" in Layers — are derived locally by appending a NOID qualifier to their parent ARK, with no additional EZID call.

If the collection already has an ARK, enter it under `Collection ARK` in `inputs.yml`. The collection CSV will be skipped and works will be linked to the existing collection. You do not need to enter a Collection Title if the collection already exists.

## Additional Services

### Image Dimensions

After images have been uploaded to the IIIF image service, use this script to fetch height and width values and write them back into the CSV.
```
python dimensions/dimensions.py path/to/input.csv
```

The script will prompt for an output directory. The updated CSV is written there with the same filename as the input.

**Requirements:**
- The CSV must have a `IIIF Access URL` column containing base IIIF image URLs
- Rows that already have both `height` and `width` values are skipped
- Rows with no `IIIF Access URL` are skipped
- A summary of fetched, skipped, or failed rows is printed when done

Re-running against the same CSV is safe as existing dimensions are preserved and only missing values are fetched.
