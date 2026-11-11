"""Real-browser validation of the added planning workflows and a real GTFS upload."""
import json
from pathlib import Path
from zipfile import ZipFile

from playwright.sync_api import sync_playwright
from smoke_dashboard import settled

ROOT=Path(__file__).resolve().parents[1]


def run():
    out=ROOT/'reports/completion/browser';out.mkdir(parents=True,exist_ok=True)
    errors=[]
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='chromium',headless=True)
        page=browser.new_page(viewport={'width':1440,'height':1100})
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto('http://127.0.0.1:8501',wait_until='domcontentloaded')
        page.get_by_text('Route review register',exact=True).wait_for(timeout=90000)
        settled(page)
        for title in ['Route comparison','Budget allocation','Planning proposals','GTFS import','Observed-load classification']:
            print('Checking '+title,flush=True)
            page.get_by_text(title,exact=True).first.click()
            page.get_by_role('heading',name=title,exact=True).wait_for(timeout=60000)
            if title=='GTFS import':
                page.get_by_text('Upload a GTFS ZIP containing',exact=False).wait_for(timeout=30000)
            elif title=='Observed-load classification':
                page.get_by_role('button',name='Download required label-file header',exact=True).wait_for(timeout=30000)
            else:
                settled(page)
            assert page.locator('[data-testid="stException"]').count()==0
            if title=='Budget allocation':
                with page.expect_download() as transfer:
                    page.get_by_role('button',name='Download allocation and assumptions',exact=True).click()
                transfer.value.save_as(out/'allocation.zip')
                with ZipFile(out/'allocation.zip') as archive:
                    assumptions=json.loads(archive.read('assumptions.json'))
                    assert assumptions['spent_added_bus_hours']<=50+1e-8
                    assert assumptions['passenger_benefit_measured'] is False
            if title=='Planning proposals':
                page.get_by_role('button',name='Save proposal',exact=True).click()
                page.get_by_text('Saved local proposals',exact=True).wait_for()
                settled(page)
                assert page.locator('[data-testid="stAlert"]').filter(has_text='Proposal saved:').count()>0
            if title=='GTFS import':
                print('Uploading real GTFS archive',flush=True)
                page.locator('input[type=file]').set_input_files(str(ROOT/'data/raw/new_york/gtfs/archive/manhattan_20260903.zip'))
                page.get_by_role('button',name='Validate and inspect schedule',exact=True).wait_for(timeout=60000)
                page.get_by_role('button',name='Validate and inspect schedule',exact=True).click()
                print('Inspecting uploaded archive',flush=True)
                page.get_by_text('Schedule inspection complete. This is project-field validation, not full GTFS certification.',exact=True).wait_for(timeout=180000)
                page.get_by_role('button',name='Save validated import locally',exact=True).wait_for(timeout=60000)
                assert page.locator('[data-testid="stException"]').count()==0
            if title=='Observed-load classification':
                with page.expect_download() as header:
                    page.get_by_role('button',name='Download required label-file header',exact=True).click()
                header.value.save_as(out/'labels_header.csv')
                assert len((out/'labels_header.csv').read_text().splitlines())==1
            page.screenshot(path=str(out/(title.lower().replace(' ','_')+'.png')),full_page=True)
        browser.close()
    assert not errors,errors
    result={'new_pages':5,'real_gtfs_upload_passed':True,'allocation_download_verified':True,
            'proposal_save_passed':True,'label_template_contains_observations':False,'javascript_errors':errors}
    (out/'result.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))


if __name__=='__main__':run()
