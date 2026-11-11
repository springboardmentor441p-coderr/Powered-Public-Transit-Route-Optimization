"""Verify packaged UI and persisted API products in the selected Python environment."""
import json,subprocess,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from backend.main import app
out=Path('reports/application_acceptance')
with TestClient(app) as client:
 health=client.get('/api/health');assert health.status_code==200,health.text
 home=client.get('/');assert home.status_code==200 and 'RouteRanker' in home.text
 routes=client.get('/api/routes');assert routes.status_code==200 and len(routes.json()['items'])==41
 models=client.get('/api/models');assert models.status_code==200
report={'python':sys.version,'executable':sys.executable,'database':health.json(),'built_frontend_served':True,'routes':41,'models_available':bool(models.json()['items'])}
(out/'isolated_setup.json').write_text(json.dumps(report,indent=2))
with (out/'application_environment.txt').open('w',encoding='utf-8') as f:subprocess.run([sys.executable,'-m','pip','freeze'],stdout=f,check=True)
print(json.dumps(report,indent=2))
