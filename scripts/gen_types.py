#!/usr/bin/env python3
"""Generate app/frontend/src/types/generated.ts from Pydantic models.

This is the codegen step that retires the hand-synced TypeScript interfaces
in ``app/backend/src/types/models.ts`` and ``app/frontend/src/types/models.ts``.
See ``todo/PYTHON_BACKEND.md`` for the migration plan; this script is the
Phase 0 deliverable.

The script imports every concrete Pydantic ``BaseModel`` subclass under
``specodex.models.*`` into a single shim module, then hands that module to
``pydantic2ts`` for TypeScript emission. ``pydantic2ts`` shells out to
``npx json-schema-to-typescript`` — Node 18+ must be on PATH.

Run via:

    ./Quickstart gen-types

CI fails if the committed ``generated.ts`` drifts from source; see
``.github/workflows/ci.yml``.
"""

from __future__ import annotations

import importlib
import inspect
import sys
import types
from pathlib import Path

from pydantic import BaseModel
from pydantic2ts import generate_typescript_defs


ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "app" / "frontend" / "src" / "types" / "generated.ts"

# Modules under ``specodex.models`` that hold Pydantic classes. ``llm_schema``
# is excluded because it builds Gemini-shaped schemas at runtime, not domain
# models, and ``common`` exports types we want re-exported through the
# product modules' fields.
_MODEL_MODULES = (
    "specodex.models.common",
    "specodex.models.product",
    "specodex.models.datasheet",
    "specodex.models.manufacturer",
    "specodex.models.motor",
    "specodex.models.drive",
    "specodex.models.gearhead",
    "specodex.models.robot_arm",
    "specodex.models.contactor",
    "specodex.models.electric_cylinder",
    "specodex.models.linear_actuator",
)


def _build_shim_module() -> types.ModuleType:
    """Return a synthetic module whose namespace contains every BaseModel.

    ``pydantic2ts`` walks the module namespace looking for Pydantic
    ``BaseModel`` subclasses; auto-discovering across the ``specodex.models``
    package by hand keeps the public ``__init__`` lean (it currently exports
    only ``Manufacturer``).
    """
    shim = types.ModuleType("specodex_models_codegen_shim")
    seen: set[str] = set()
    for mod_path in _MODEL_MODULES:
        mod = importlib.import_module(mod_path)
        for name, obj in inspect.getmembers(mod, inspect.isclass):
            if not issubclass(obj, BaseModel) or obj is BaseModel:
                continue
            if obj.__module__ != mod_path:
                # skip re-exports (e.g. ValueUnit imported into motor.py)
                continue
            if name in seen:
                continue
            setattr(shim, name, obj)
            seen.add(name)
    return shim


def main() -> int:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    shim = _build_shim_module()
    sys.modules[shim.__name__] = shim

    # pydantic2ts shells out to ``json2ts`` (json-schema-to-typescript). We
    # don't want to require a global npm install — ``npx --yes`` resolves
    # the binary on demand, and pydantic2ts allows multi-word commands
    # (it skips its ``shutil.which`` precheck when the command contains a
    # space — see pydantic2ts/cli/script.py).
    generate_typescript_defs(
        shim.__name__,
        str(OUTPUT),
        json2ts_cmd="npx --yes json-schema-to-typescript",
    )

    banner = (
        "/* eslint-disable */\n"
        "/**\n"
        " * AUTO-GENERATED — do not edit by hand.\n"
        " * Regenerate with: ./Quickstart gen-types\n"
        " * Source: specodex/models/*.py (Pydantic BaseModel subclasses)\n"
        " * Plan:   todo/PYTHON_BACKEND.md\n"
        " */\n\n"
    )
    OUTPUT.write_text(banner + OUTPUT.read_text())
    print(f"wrote {OUTPUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
