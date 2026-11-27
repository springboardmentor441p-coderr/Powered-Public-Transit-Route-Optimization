"""Headless smoke test of every Streamlit page (requires trained artefacts).

    python tests/smoke_pages.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "app")]

from streamlit.testing.v1 import AppTest  # noqa: E402

pages = sorted((ROOT / "app" / "views").glob("*.py"))
failed = 0
for p in pages:
    at = AppTest.from_file(str(p), default_timeout=240)
    at.run()
    errs = [e.value for e in at.exception] + [e.body for e in at.error]
    status = "OK " if not errs else "ERR"
    failed += bool(errs)
    print(f"{status} {p.name}: {len(at.get('plotly_chart'))} charts, {len(at.dataframe)} tables, {len(at.metric)} metrics")
    for e in errs:
        print("     ", str(e)[:1500])
sys.exit(1 if failed else 0)
