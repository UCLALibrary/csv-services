"""Resolve which metadata columns belong in a CSV, per level and preset.

Reads field_definitions.yaml — see that file for the tier/tag/level model.

This module decides which *columns* exist. What *value* goes in them is up to
each script: multipart, for instance, writes "multi-part" into viewingHint on
its IIIF-Collection work rows regardless of any user-supplied default.
"""

import os

import yaml

DEFAULT_PRESET = "required_recommended"

_PATH = os.path.join(os.path.dirname(__file__), "field_definitions.yaml")
_definitions = None


def _load():
    global _definitions
    if _definitions is None:
        with open(_PATH) as f:
            _definitions = yaml.safe_load(f)
    return _definitions


def headers(level, preset=DEFAULT_PRESET):
    """Ordered metadata columns for a level ('collection' or 'work').

    The required tier is always included. The default preset adds the
    recommended tier; a named preset instead adds fields carrying its tag.
    Column order follows field_definitions.yaml, so reordering that file
    reorders the CSV.
    """
    defs = _load()
    if preset not in defs["presets"]:
        raise ValueError(
            f"Unknown preset {preset!r} — expected one of {sorted(defs['presets'])}"
        )
    tag = (defs["presets"][preset] or {}).get("tag")

    out = []
    for name, spec in defs["fields"].items():
        tier = (spec.get("levels") or {}).get(level)
        if tier is None:
            continue
        if tier == "required":
            include = True
        elif preset == DEFAULT_PRESET:
            include = tier == "recommended"
        else:
            include = tag in (spec.get("tags") or [])
        if include:
            out.append(name)
    return out


def preset_defaults(preset):
    """Values a preset pre-fills, e.g. ARCE's fixed Repository."""
    return dict((_load()["presets"].get(preset) or {}).get("defaults") or {})


def presets():
    """Preset name -> description, for building a selector."""
    return {
        name: (spec or {}).get("description", name)
        for name, spec in _load()["presets"].items()
    }


def combine(*groups):
    """Concatenate column groups, dropping duplicates and keeping first order."""
    seen = set()
    out = []
    for group in groups:
        for name in group:
            if name not in seen:
                seen.add(name)
                out.append(name)
    return out
