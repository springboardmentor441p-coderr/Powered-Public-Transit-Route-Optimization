"""Real-browser acceptance against the local React/API/PostgreSQL application."""
from pathlib import Path
import json,urllib.request
from playwright.sync_api import sync_playwright
OUT=Path('reports/application_acceptance');OUT.mkdir(parents=True,exist_ok=True)
def request(path,body=None):
 r=urllib.request.Request('http://127.0.0.1:8000/api/'+path,data=json.dumps(body).encode() if body is not None else None,headers={'Content-Type':'application/json'})
 return json.load(urllib.request.urlopen(r,timeout=180))
results=[]
with sync_playwright() as w:
 b=w.chromium.launch(channel='chromium',headless=True);p=b.new_page(viewport={'width':1440,'height':1000});errors=[];p.on('pageerror',lambda e:errors.append(str(e)))
 p.goto('http://127.0.0.1:5173');p.get_by_role('heading',name='Overview',exact=True).wait_for()
 for name in ['Overview','Review priorities','Route detail','Compare routes','Route groups','Forecasts','Scenarios','Replay']:
  p.get_by_role('button',name=name,exact=True).click();p.wait_for_timeout(1800)
  assert not p.get_by_role('alert').count(),(name,p.get_by_role('alert').all_text_contents())
  results.append({'screen':name,'passed':True})
 p.get_by_role('button',name='Create replay',exact=True).click();p.get_by_role('status').wait_for(state='hidden',timeout=180000);assert not p.get_by_role('alert').count()
 p.get_by_role('button',name='advance',exact=True).click();p.get_by_role('status').wait_for(state='hidden',timeout=180000);assert not p.get_by_role('alert').count()
 p.get_by_role('button',name='Forecasts',exact=True).click();p.get_by_role('button',name='Forecast selected route',exact=True).click();p.get_by_role('status').wait_for(state='hidden',timeout=180000);assert not p.get_by_role('alert').count()
 p.screenshot(path=str(OUT/'forecast.png'),full_page=True)
 p.set_viewport_size({'width':390,'height':844});p.screenshot(path=str(OUT/'mobile.png'),full_page=True)
 assert not errors,errors;b.close()
s=request('replays',{'start_date':'2026-06-01','end_date':'2026-07-31','speed_seconds':5})
f=request('forecasts',{'route':'M34+','target_date':s['virtual_date'],'session_id':s['id']});assert f['actual'] is None
f2=request('forecasts',{'route':'M34+','target_date':s['virtual_date'],'session_id':s['id']});assert f2['id']==f['id']
sc=request('scenarios',{'route':'M34+','date':'2026-06-01','proposed_trips':0,'demand_source':'forecast','forecast_id':f['id'],'session_id':s['id']})
assert sc['proposed']['rides_per_trip'] is None and sc['proposed']['scheduled_hours']==0
request('replays/'+s['id']+'/control',{'action':'advance','days':15})
fs=request('forecasts?session_id='+s['id'])['items'];revealed=next(x for x in fs if x['id']==f['id']);assert revealed['actual'] is not None and revealed['prediction']==f['prediction']
child=request('replays/'+s['id']+'/control',{'action':'reset'});assert child['id']!=s['id'] and child['parent_session_id']==s['id']
report={'browser':results,'javascript_errors':errors,'forecast_idempotency':True,'delayed_actual_reveal':True,'zero_service_scenario':True,'reset_preserves_session':True,'health':request('health')}
(OUT/'browser_acceptance.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
