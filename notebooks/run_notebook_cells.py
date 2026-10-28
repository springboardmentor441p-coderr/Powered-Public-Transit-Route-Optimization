"""
Executes the code cells of notebooks/RouteRanker_EDA_and_Modeling.ipynb
and stores actual stdout, displays, and matplotlib figures in the cell outputs.
"""

import sys
import json
import base64
import io
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE_ROOT))

NB_PATH = WORKSPACE_ROOT / "notebooks" / "RouteRanker_EDA_and_Modeling.ipynb"

def run_notebook():
    with open(NB_PATH, "r", encoding="utf-8") as f:
        nb = json.load(f)

    global_env = {"__name__": "__main__"}
    execution_counter = 1

    for i, cell in enumerate(nb["cells"]):
        if cell["cell_type"] != "code":
            continue

        code = "".join(cell["source"])
        print(f"\n[EXECUTING CELL {execution_counter}]...")

        # Intercept stdout
        old_stdout = sys.stdout
        buf = io.StringIO()
        sys.stdout = buf

        # Custom display function
        def custom_display(obj):
            if hasattr(obj, "to_string"):
                print(obj.to_string())
            else:
                print(str(obj))
        global_env["display"] = custom_display

        outputs = []
        try:
            exec(code, global_env)
            text_out = buf.getvalue()
            if text_out:
                outputs.append({
                    "name": "stdout",
                    "output_type": "stream",
                    "text": [line + "\n" for line in text_out.splitlines()]
                })

            # Check if any matplotlib figure was created
            fig_nums = plt.get_fignums()
            for fnum in fig_nums:
                fig = plt.figure(fnum)
                img_buf = io.BytesIO()
                fig.savefig(img_buf, format="png", bbox_inches="tight", dpi=100)
                img_buf.seek(0)
                b64 = base64.b64encode(img_buf.read()).decode("utf-8")
                outputs.append({
                    "data": {
                        "image/png": b64,
                        "text/plain": ["<Figure size ...>"]
                    },
                    "metadata": {},
                    "output_type": "display_data"
                })
                plt.close(fig)

            cell["execution_count"] = execution_counter
            cell["outputs"] = outputs
            execution_counter += 1
            print(f"  Cell {execution_counter - 1} finished successfully ({len(outputs)} output items).")

        except Exception as e:
            text_out = buf.getvalue()
            sys.stdout = old_stdout
            print(f"  [ERROR] in Cell {execution_counter}: {e}")
            cell["execution_count"] = execution_counter
            cell["outputs"] = [{
                "ename": type(e).__name__,
                "evalue": str(e),
                "output_type": "error",
                "traceback": [f"{type(e).__name__}: {str(e)}"]
            }]
            execution_counter += 1
            break
        finally:
            sys.stdout = old_stdout

    with open(NB_PATH, "w", encoding="utf-8") as f:
        json.dump(nb, f, indent=2)

    print(f"\n[DONE] Notebook updated with real executed outputs at: {NB_PATH}")

if __name__ == "__main__":
    run_notebook()
