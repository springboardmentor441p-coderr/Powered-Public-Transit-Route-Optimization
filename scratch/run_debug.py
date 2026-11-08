import os, sys
sys.path.append('C:/Users/tdsri/Powered-Public-Transit-Route-Optimization')
from backend.scripts.seed_data import main as seed_main
seed_main()
from backend.app.main import app
from fastapi.testclient import TestClient
client = TestClient(app)
admin_email = os.getenv('ADMIN_EMAIL', 'admin@example.com')
admin_password = os.getenv('ADMIN_PASSWORD', 'admin123')
login = client.post('/auth/login', data={'username': admin_email, 'password': admin_password})
print('login', login.status_code, login.json())
admin_token = login.json()['access_token']
headers = {'Authorization': f'Bearer {admin_token}'}
payload = {'email':'operator@example.com','password':'operator123','full_name':'Operator User','role':'operator'}
resp = client.post('/auth/admin/users', json=payload, headers=headers)
print('create', resp.status_code, resp.text)

