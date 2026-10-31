"""Run the canonical notebooks in fresh kernels and require visible saved outputs."""

import argparse
import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil

import nbformat
from nbclient import NotebookClient

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("notebooks", nargs="*", help="Paths, or all four notebooks by default")
    parser.add_argument("--kernel", default="python3", help="Installed Jupyter kernel name")
    args = parser.parse_args()
    paths = [ROOT / p for p in args.notebooks] if args.notebooks else sorted(
        (ROOT / "notebooks/new_york").glob("[0-9][0-9]_*.ipynb"))
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = ROOT.parent / "router_archives" / "notebook_runs" / stamp
    backup.mkdir(parents=True, exist_ok=True)
    audit = []
    for path in paths:
        print("Running", path.name, flush=True)
        shutil.copy2(path, backup / path.name)
        notebook = nbformat.read(path, as_version=4)
        for cell in notebook.cells:
            if cell.cell_type == "code":
                cell.outputs = []
                cell.execution_count = None

        def progress(cell, cell_index, **kwargs):
            if cell.cell_type == "code":
                print(f"  cell {cell_index + 1}/{len(notebook.cells)}", flush=True)

        try:
            NotebookClient(notebook, timeout=1200, kernel_name=args.kernel,
                           resources={"metadata": {"path": str(path.parent)}},
                           on_cell_start=progress).execute()
        except Exception:
            nbformat.write(notebook, backup / (path.stem + "_failed.ipynb"))
            raise
        cells = []
        for i, cell in enumerate(notebook.cells, 1):
            if cell.cell_type != "code":
                continue
            assert cell.execution_count is not None, f"Unexecuted cell {i}"
            assert cell.outputs and not any(o.output_type == "error" for o in cell.outputs)
            assert any((o.get("text", "").strip() if o.output_type == "stream" else bool(o.get("data")))
                       for o in cell.outputs), f"No visible output in cell {i}"
            cell.metadata.update(collapsed=False, jupyter={"outputs_hidden": False})
            cells.append({"cell": i, "execution_count": cell.execution_count, "outputs": len(cell.outputs)})
        nbformat.validate(notebook)
        nbformat.write(notebook, path)
        audit.append({"notebook": path.relative_to(ROOT).as_posix(), "code_cells": len(cells),
                      "outputs": sum(c["outputs"] for c in cells), "errors": 0, "cells": cells})
        print("Saved:", len(cells), "executed cells with outputs", flush=True)
    out = ROOT / "reports/eda/notebook_execution_audit.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    previous = json.loads(out.read_text(encoding="utf-8")).get("notebooks", []) if out.exists() else []
    refreshed = {item["notebook"]: item for item in previous}
    refreshed.update({item["notebook"]: dict(item, executed_utc=stamp) for item in audit})
    out.write_text(json.dumps({"executed_utc": stamp, "notebooks": list(refreshed.values())}, indent=2), encoding="utf-8")


if __name__ == "__main__":
    if hasattr(asyncio, "WindowsSelectorEventLoopPolicy"):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    main()
