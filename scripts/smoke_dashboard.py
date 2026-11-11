"""Optional real-browser smoke check. Start Streamlit before running this script."""
import argparse
import json
from pathlib import Path
from zipfile import ZipFile

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def settled(page):
    page.wait_for_timeout(250)
    page.wait_for_function("() => !document.querySelector('[data-testid=\"stStatusWidget\"]') && !document.querySelector('[data-stale=\"true\"]')", timeout=90000)
    page.wait_for_timeout(700)


def run(url):
    output = ROOT / "reports/dashboard/browser"
    output.mkdir(parents=True, exist_ok=True)
    errors, pages = [], []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, channel="chromium")
        page = browser.new_page(viewport={"width": 1440, "height": 1080}, device_scale_factor=1)
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(url, wait_until="domcontentloaded")
        page.get_by_text("Route review register", exact=True).wait_for(timeout=90000)
        settled(page)
        for title in ["Overview", "Route explorer", "Demand forecasts", "Planning review", "Service scenarios", "Data coverage"]:
            page.get_by_text(title, exact=True).first.click()
            if title != "Overview":
                page.get_by_role("heading", name=title, exact=True).wait_for(timeout=60000)
            settled(page)
            if page.locator('[data-testid="stException"]').count():
                raise AssertionError(page.locator('[data-testid="stException"]').inner_text())
            page.screenshot(path=str(output / (title.lower().replace(" ", "_") + ".png")), full_page=True)
            pages.append(title)
        page.get_by_text("Route explorer", exact=True).first.click()
        settled(page)
        page.get_by_role("tab", name="Route geometry").click()
        page.wait_for_timeout(2500)
        page.screenshot(path=str(output / "route_map.png"), full_page=True)
        page.get_by_text("Service scenarios", exact=True).first.click()
        settled(page)
        download_button = page.get_by_role("button", name="Download scenario with assumptions", exact=True)
        download_button.wait_for(timeout=30000)
        with page.expect_download() as download:
            download_button.click()
        downloaded = output / "downloaded_scenario.zip"
        download.value.save_as(downloaded)
        with ZipFile(downloaded) as archive:
            assumptions = json.loads(archive.read("assumptions.json"))
            assert assumptions["automatic_service_change"] is False
            assert assumptions["route"] == "M34+"
            assert "scenario.csv" in archive.namelist()
        page.get_by_role("tab", name="Transfer bus-hours").click()
        page.wait_for_timeout(500)
        page.screenshot(path=str(output / "transfer.png"), full_page=True)
        page.get_by_text("Data coverage", exact=True).first.click()
        settled(page)
        page.get_by_text("Local data release and integrity", exact=True).click()
        page.get_by_role("button", name="Verify all dashboard inputs", exact=True).click()
        page.get_by_text("All 27 dashboard inputs match this release.", exact=True).wait_for(timeout=60000)
        settled(page)
        page.set_viewport_size({"width": 390, "height": 844})
        collapse = page.get_by_role("button", name="Collapse sidebar")
        if collapse.count() and collapse.is_visible():
            collapse.click()
        page.wait_for_timeout(500)
        page.screenshot(path=str(output / "mobile_coverage.png"), full_page=True)
        browser.close()
    if errors:
        raise AssertionError(errors)
    result = {"pages_rendered": pages, "javascript_errors": errors, "download_verified": True, "integrity_check_passed": True}
    (output / "smoke_result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8501")
    run(parser.parse_args().url)
