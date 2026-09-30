"""Exercise the local demo in a real headless Chrome browser.

Requires: pip install -r requirements-browser.txt
Run with the demo server already listening at 127.0.0.1:8000.
"""
import json
import os
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "output/browser"
OUTPUT.mkdir(parents=True, exist_ok=True)
BASE_URL = os.getenv("BRON_TEST_URL", "http://127.0.0.1:8000")


def login(page, username):
    page.goto(BASE_URL + "/login/")
    page.get_by_label("Username", exact=True).fill(username)
    page.get_by_label("Password", exact=True).fill("Bron-demo-2026!")
    page.get_by_role("button", name="Sign in", exact=True).click()
    expect(page.get_by_role("heading", name=f"Hello, {'Lotte' if username == 'lotte' else 'Sarah'}.")).to_be_visible()


def run():
    results = []
    with sync_playwright() as engine:
        channel = os.getenv("BRON_BROWSER_CHANNEL", "chrome")
        browser = engine.chromium.launch(**({"channel": channel} if channel != "chromium" else {}), headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 1050}, device_scale_factor=1)
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(BASE_URL + "/login/")
        page.screenshot(path=str(OUTPUT / "login-desktop.png"), full_page=True)
        login(page, "lotte")
        expect(page.get_by_role("heading", name="My clients 5")).to_be_visible()
        page.screenshot(path=str(OUTPUT / "overview-desktop.png"), full_page=True)
        results.append("Consultant login and dashboard")
        page.get_by_role("link").filter(has=page.get_by_role("heading", name="Bakkerij Janssens")).click()
        page.get_by_role("link").filter(has=page.get_by_role("heading", name="Payroll input", exact=True)).click()
        expect(page.get_by_role("heading", name="Applicable knowledge 3")).to_be_visible()
        expect(page.get_by_text("Found but not applicable")).to_be_visible()
        page.screenshot(path=str(OUTPUT / "payroll-topic-desktop.png"), full_page=True)
        results.append("Client/topic knowledge and excluded country")
        page.set_viewport_size({"width": 390, "height": 844})
        page.wait_for_function("document.querySelector('.sidebar').getBoundingClientRect().right <= 0")
        page.screenshot(path=str(OUTPUT / "payroll-topic-mobile.png"), full_page=True)
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), "Mobile page overflows horizontally"
        page.get_by_role("button", name="Toggle navigation").click()
        expect(page.get_by_role("link", name="Sources", exact=True)).to_be_visible()
        page.get_by_role("button", name="Toggle navigation").click()
        results.append("Mobile viewport and navigation")
        page.set_viewport_size({"width": 1440, "height": 1050})
        page.get_by_role("link", name="Sources", exact=True).first.click()
        page.get_by_role("link").filter(has=page.get_by_text("Correction deadline BE", exact=True)).click()
        page.get_by_role("link").filter(has=page.get_by_text("Correction deadline BE", exact=True)).click()
        page.get_by_label("Your action").select_option("source_outdated")
        page.get_by_label("Reason (required)").fill("Browser smoke: route the obsolete procedure to its responsible team.")
        page.get_by_role("button", name="Save decision").click()
        expect(page.get_by_text("Your decision was saved and added to the audit trail.")).to_be_visible()
        results.append("Consultant flags outdated source via HTMX")
        page.get_by_role("button", name="Sign out").click()
        login(page, "sarah")
        page.get_by_role("link", name="Sources", exact=True).first.click()
        page.get_by_role("link").filter(has=page.get_by_text("Correction deadline BE", exact=True)).click()
        page.get_by_role("link").filter(has=page.get_by_text("Correction deadline BE", exact=True)).click()
        page.get_by_label("Your action").select_option("supersede")
        page.get_by_label("Replacement passage").select_option(label="Working instructions")
        page.get_by_label("Reason (required)").fill("Browser smoke: current working instructions replace the expired deadline.")
        page.get_by_role("button", name="Save decision").click()
        expect(page.get_by_text("Superseded by")).to_be_visible()
        results.append("Owner supersedes obsolete procedure")
        page.get_by_role("link", name="Sources", exact=True).first.click()
        page.get_by_role("link").filter(has=page.get_by_text("Working instructions", exact=True)).click()
        page.get_by_role("button", name="Check evidence").click()
        expect(page.get_by_role("heading", name="Follow the evidence.")).to_be_visible()
        expect(page.get_by_text("Synthetic demo fixture (unverified)", exact=True)).to_be_visible()
        results.append("Offline structured evidence check")
        page.get_by_role("link", name="Sources", exact=True).first.click()
        page.get_by_role("link").filter(has=page.get_by_text("Telework allowance · PC 200", exact=True)).click()
        page.get_by_role("link", name="Upload new version").click()
        page.get_by_label("File", exact=True).set_input_files(str(ROOT / "seed/sources/telework-v2.md"))
        page.get_by_label("Effective from", exact=True).fill("2027-01-01T00:00")
        page.get_by_role("button", name="Upload & check impact").click()
        expect(page.get_by_role("heading", name="One change. Clear impact.")).to_be_visible()
        expect(page.locator(".stat-card").filter(has_text="Unchanged passages").locator(".stat-value")).to_have_text("8")
        expect(page.locator(".stat-card").filter(has_text="Passages to review").locator(".stat-value")).to_have_text("1")
        expect(page.locator(".stat-card").filter(has_text="Dependent exceptions").locator(".stat-value")).to_have_text("1")
        page.screenshot(path=str(OUTPUT / "ripple-desktop.png"), full_page=True)
        results.append("Source upload and 8/1/1 ripple")
        assert not errors, errors
        browser.close()
    report = {"passed": results, "javascript_errors": errors, "screenshots": str(OUTPUT)}
    (OUTPUT / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    run()
