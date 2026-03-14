import io
import os
import pathlib
import sys
import tempfile
import zipfile

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Ensure repo root is in path so `core` package is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from core import layers, multipart, standard

app = FastAPI()

SCRIPTS = {
    "standard": standard,
    "multipart": multipart,
    "layers": layers,
}


class GenerateRequest(BaseModel):
    script: str
    root_path: str
    tree: list[str]
    config: dict


def _safe_join(base: pathlib.Path, relative: str) -> pathlib.Path:
    """Resolve relative path, raising 400 if it escapes base."""
    full = (base / relative).resolve()
    if not str(full).startswith(str(base.resolve()) + os.sep):
        raise HTTPException(status_code=400, detail=f"Invalid path in tree: {relative!r}")
    return full


@app.post("/api/generate")
async def generate(req: GenerateRequest):
    if req.script not in SCRIPTS:
        raise HTTPException(status_code=400, detail=f"Unknown script type: {req.script!r}")

    if not req.root_path.strip():
        raise HTTPException(status_code=400, detail="root_path is required")

    if not req.tree:
        raise HTTPException(status_code=400, detail="No files in tree — select a folder first")

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = pathlib.Path(tmp)

        # Build empty scaffold matching the user's folder structure
        for rel in req.tree:
            target = _safe_join(tmp_path, rel)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.touch()

        try:
            outputs = SCRIPTS[req.script].run(
                scan_path=str(tmp_path),
                base_path=req.root_path.rstrip("/\\"),
                config=req.config,
            )
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for filename, content in outputs.items():
            zf.writestr(filename, content)
    zip_buf.seek(0)

    prefix = req.config.get("Collection Shortcode") or req.config.get("Collection Title") or "output"
    download_name = f"{prefix}-csvs.zip"

    return StreamingResponse(
        zip_buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{download_name}"'},
    )


# Static files last so API routes take precedence
_static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/", StaticFiles(directory=_static_dir, html=True), name="static")
