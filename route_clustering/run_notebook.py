import nbformat, os, sys
from nbconvert.preprocessors import ExecutePreprocessor

nb_path = r'C:\Users\kavyasri\Downloads\mtc-gtfs\route_clustering\06_route_clustering.ipynb'

with open(nb_path, encoding='utf-8') as f:
    nb = nbformat.read(f, as_version=4)

ep = ExecutePreprocessor(timeout=600, kernel_name='python3')

try:
    ep.preprocess(nb, {'metadata': {'path': os.path.dirname(nb_path)}})
except Exception as e:
    print('Execution error:', e)
    sys.exit(1)

# Write executed notebook back
with open(nb_path, 'w', encoding='utf-8') as f:
    nbformat.write(nb, f)

print('Notebook executed successfully')
