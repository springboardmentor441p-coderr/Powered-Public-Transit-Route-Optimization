"""Headless smoke test of every Streamlit page in frontend/main.py (requires trained artefacts).

    python tests/smoke_pages.py
"""
import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
from streamlit.testing.v1 import AppTest  # noqa: E402

tree = ast.parse((ROOT / "frontend" / "main.py").read_text(encoding="utf-8"))
pages = [n.name for n in tree.body if isinstance(n, ast.FunctionDef) and n.name.startswith("page_")]
failed = 0
for fn in pages:
    script = (f"import sys\nsys.path.insert(0, r'{ROOT}')\n"
              f"from frontend import main as fe\nfe.{fn}()\n")
    at = AppTest.from_string(script, default_timeout=240)
    at.run()
    errs = [e.value for e in at.exception] + [e.body for e in at.error]
    failed += bool(errs)
    print(f"{'ERR' if errs else 'OK '} {fn}: {len(at.get('plotly_chart'))} charts, {len(at.dataframe)} tables, "
          f"{len(at.metric)} metrics")
    for e in errs:
        print("     ", str(e)[:1500])
print(f"{len(pages) - failed}/{len(pages)} pages OK")
sys.exit(1 if failed else 0)
