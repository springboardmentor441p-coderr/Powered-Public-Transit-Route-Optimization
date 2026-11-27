"""Capture dashboard screenshots with Playwright driving an installed Chromium browser (Edge or Chrome).

    python scripts/capture_screenshots.py     -> reports/figures/screens/*.png
"""
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports" / "figures" / "screens"
OUT.mkdir(parents=True, exist_ok=True)
PORT = 8599
PAGES = ["", "best_route", "productivity_ranking", "route_comparison", "historical_replay", "eda_insights",
         "scenario_simulator", "recommendations", "model_performance", "data_coverage", "pipeline_architecture"]
BROWSERS = [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            shutil.which("chromium") or "", shutil.which("google-chrome") or ""]


def main():
    browser = next((b for b in BROWSERS if b and Path(b).exists()), None)
    if not browser:
        sys.exit("No Chromium-based browser found")
    srv = subprocess.Popen([sys.executable, "-m", "streamlit", "run", "frontend/main.py", "--server.port", str(PORT),
                            "--server.headless", "true"], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(60):
            try:
                urllib.request.urlopen(f"http://localhost:{PORT}/_stcore/health", timeout=2)
                break
            except Exception:
                time.sleep(1)
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            br = pw.chromium.launch(executable_path=browser, headless=True)
            page = br.new_page(viewport={"width": 1500, "height": 1000}, device_scale_factor=1)
            for p in PAGES:
                name = p or "network_overview"
                out = OUT / f"{name}.png"
                page.goto(f"http://localhost:{PORT}/{p}", wait_until="networkidle", timeout=180000)
                page.wait_for_selector("div.rr-hero", timeout=180000)
                # wait until Streamlit has finished running the script
                page.wait_for_function("""() => !document.querySelector('[data-testid="stStatusWidget"]')""",
                                       timeout=240000)
                page.wait_for_timeout(6000)
                page.screenshot(path=str(out), full_page=False)
                print("saved", out)
            br.close()
    finally:
        srv.terminate()


if __name__ == "__main__":
    main()
