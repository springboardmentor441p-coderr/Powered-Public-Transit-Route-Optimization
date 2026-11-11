"""Browser checks for linked route maps and scenario persistence."""
from pathlib import Path
import json
from playwright.sync_api import sync_playwright
with sync_playwright() as w:
    browser = w.chromium.launch(channel="chromium")
    page = browser.new_page(viewport={"width":1440,"height":1000})
    page.goto("http://127.0.0.1:5173")
    page.locator(".leaflet-overlay-pane path").first.wait_for(timeout=60000)
    page.locator(".leaflet-overlay-pane path").first.dispatch_event("click")
    page.get_by_role("heading", name="Route detail", exact=True).wait_for()
    page.get_by_role("button", name="Scenarios", exact=True).click()
    page.get_by_role("status").wait_for(state="hidden",timeout=60000)
    page.get_by_label("Proposed scheduled trips").fill("0")
    with page.expect_response(lambda r:r.url.endswith("/api/scenarios") and r.request.method=="POST",timeout=60000) as response:
        page.get_by_role("button", name="Calculate and save scenario",exact=True).click()
    assert response.value.status==201,response.value.text()
    saved=response.value.json()
    assert saved["proposed"]["scheduled_trips"]==0
    page.get_by_role("columnheader",name="Proposed",exact=True).first.wait_for()
    assert not page.get_by_role("alert").count()
    page.screenshot(path="reports/application_acceptance/scenario_workspace.png",full_page=True)
    Path("reports/application_acceptance/planning_interactions.json").write_text(json.dumps({"map_selects_route_detail":True,"scenario_saved_from_ui":True,"scenario_id":saved["id"],"zero_service_table_visible":True}))
    browser.close()
    print("Map selection and saved UI scenario passed")
