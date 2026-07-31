# Digital Collections CSV Services

Tools for generating and enriching CSVs for digital collections processing and ingest. Available as a hosted web app or as local command-line scripts.

---

## Web App

Use the hosted app at **https://digital-collections-csv-services.onrender.com/**

### Generate CSVs

#### Collection Types

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

### Additional Services

#### Image Dimensions

Upload a CSV with a `IIIF Access URL` column. The service fetches height and width from each image's `info.json` endpoint and writes them back to the CSV. Rows that already have both values are skipped.

Use this after CSVs have been generated and images have been uploaded to your IIIF image service.

---

## Form Fields

### Collection folder
The full path to the collection folder on your system (e.g. `Masters/dlmasters/my-collection`). Include the collection folder itself, not just its parent.

### Collection
- **Collection Shortcode** — Short identifier used as the CSV filename prefix. Should be consistent across all batches for the same collection.
- **Collection Title** — Display title. Required for new collections; leave blank if the collection already exists.
- **Collection ARK** — Required if the collection already exists. Works will be linked to it and no collection CSV will be generated. Leave blank if creating a new collection.

### Metadata Defaults
These values are applied to all works in the collection. All fields are optional.

`Visibility` `Genre` `Repository` `Language` `Date.created` `Date.normalized` `Type.typeOfResource` `Rights.copyrightStatus` `Rights.servicesContact`

### Type-specific defaults

**Standard — Work & Page Defaults**
- `viewingHint` — e.g. `paged` or `continuous`
- `Text direction`
- `page title prefix` — e.g. `Page` produces "Page 1", "Page 2", …
- `File extensions` — comma-separated (e.g. `.tif,.jpg`); leave blank to include all files

**Multipart — Volume & Page Defaults**
- `viewingHint`, `Text direction`
- `vol title prefix` — e.g. `Volume` produces "Volume 1", "Volume 2", …
- `page title prefix`

**Layers — Page & Layer Defaults**
- `viewingHint`, `Text direction`
- `page title prefix`
- `Layer Type` — `Choice` or `Layer`
- `layer title prefix` — e.g. `Layer` produces "Layer 1", "Layer 2", …
- `File extensions`

### Importing an existing inputs.yml
You can drag and drop an `inputs.yml` file onto the form to pre-populate the fields. EZID credentials in the file will also be applied.

---

## ARK Minting

EZID credentials are optional. Without them, the scripts generate placeholder ARKs in the format `ark:/FAKE/...`, which is useful for testing and reviewing the CSV structure before a real ingest run.

When credentials are provided, the script mints a real ARK via EZID for each collection, work, volume (Multipart), and page (Layers). ARKs for items that carry an image file path — pages in Standard and Multipart, and layers in Layers — are derived locally by appending a NOID qualifier to their parent ARK, with no additional EZID call.

If the collection already has an ARK, enter it in the **Collection ARK** field. The collection CSV will be skipped and works will be linked to the existing collection.

**EZID Credentials** — `EZID Username`, `EZID Password`, `ARK Shoulder` (e.g. `ark:/21198/z1`). Credentials are used only for the current request and are never stored.

---

## Using Local Scripts

For installation and usage instructions, see the [main branch README](https://github.com/UCLALibrary/csv-services/blob/main/README.md).

### Image Dimensions

```
python dimensions/dimensions.py input.csv
```

Prompts for an output directory and writes the updated CSV there. Requires a `IIIF Access URL` column in the input CSV.
