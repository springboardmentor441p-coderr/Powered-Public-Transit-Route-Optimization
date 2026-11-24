import json, os, sys, traceback
import nbformat

nb_path = r'C:\Users\kavyasri\Downloads\mtc-gtfs\route_clustering\06_route_clustering.ipynb'

with open(nb_path, encoding='utf-8') as f:
    nb = nbformat.read(f, as_version=4)

# Execution environment
global_ns = {}
local_ns = None

for i, cell in enumerate(nb.cells):
    if cell.cell_type != 'code':
        continue
    code = cell.source
    print(f'--- Executing cell {i+1} ---')
    try:
        exec(code, global_ns, local_ns)
    except Exception:
        print(f'Error in cell {i+1}:')
        traceback.print_exc()
        sys.exit(1)

# After execution, write outputs we care about
out_dir = r'C:\Users\kavyasri\Downloads\mtc-gtfs\route_clustering'
# Save cluster assignments if variable exists
assign_path = os.path.join(out_dir, 'route_cluster_assignments.csv')
if 'route_attrs' in global_ns:
    try:
        cols = ['route_id','kmeans_cluster','agg_cluster']
        if 'dbscan_cluster' in global_ns['route_attrs'].columns:
            cols.append('dbscan_cluster')
        global_ns['route_attrs'][cols].to_csv(assign_path, index=False)
        print('Cluster assignments saved to', assign_path)
    except Exception:
        traceback.print_exc()

# Save report
report_path = os.path.join(out_dir, 'route_clustering_report.md')
if 'report_path' in globals():
    # already written by notebook code
    pass
else:
    # Create minimal report
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write('# Route Clustering Report\n')
        f.write('Execution completed without full notebook generation.\n')
    print('Report written to', report_path)

print('Script completed successfully')
