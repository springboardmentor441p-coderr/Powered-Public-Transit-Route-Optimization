import io
import sys
import traceback
from contextlib import redirect_stdout, redirect_stderr
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.show = lambda *args, **kwargs: None
import nbformat
from pathlib import Path

nb_path = Path(r'C:\Users\kavyasri\Downloads\mtc-gtfs\route_clustering\06_route_clustering.ipynb')
with open(nb_path, 'r', encoding='utf-8') as f:
    nb = nbformat.read(f, as_version=4)

global_env = {'__name__': '__main__'}
execution_count = 1

for i, cell in enumerate(nb.cells):
    if cell.cell_type != 'code':
        continue
    
    print(f"Executing Code Cell {execution_count} (index {i})...")
    cell.outputs = []
    cell.execution_count = execution_count
    
    stdout_buf = io.StringIO()
    stderr_buf = io.StringIO()
    
    try:
        with redirect_stdout(stdout_buf), redirect_stderr(stderr_buf):
            exec(cell.source, global_env)
        
        out_text = stdout_buf.getvalue()
        err_text = stderr_buf.getvalue()
        
        if out_text:
            cell.outputs.append(nbformat.v4.new_output(
                output_type='stream',
                name='stdout',
                text=out_text
            ))
            print(f"  [Cell {execution_count} stdout]: {out_text.strip()[:100]}...")
            
        if err_text:
            cell.outputs.append(nbformat.v4.new_output(
                output_type='stream',
                name='stderr',
                text=err_text
            ))
            
    except Exception as e:
        err_str = traceback.format_exc()
        print(f"  Error in Cell {execution_count}: {err_str}")
        cell.outputs.append(nbformat.v4.new_output(
            output_type='error',
            ename=type(e).__name__,
            evalue=str(e),
            traceback=err_str.splitlines()
        ))
        raise e
        
    execution_count += 1

# Write back executed notebook
with open(nb_path, 'w', encoding='utf-8') as f:
    nbformat.write(nb, f)

print(f"\nSuccessfully executed all {execution_count-1} code cells and saved outputs to {nb_path}!")
