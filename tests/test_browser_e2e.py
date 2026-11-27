import time
from playwright.sync_api import sync_playwright

def run_browser_verification():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})

        # Track console messages and errors
        console_logs = []
        page.on("console", lambda msg: console_logs.append(f"[{msg.type}] {msg.text}"))
        errors = []
        page.on("pageerror", lambda err: errors.append(str(err)))

        print("Navigating to http://127.0.0.1:8050/ ...")
        page.goto("http://127.0.0.1:8050/")
        page.wait_for_selector(".kpi-card", timeout=5000)
        time.sleep(1)

        # 1. Capture Marey Chart initial state
        page.screenshot(path="test_browser_marey.png")
        print("Captured test_browser_marey.png")

        # 1b. Test Track Schematic
        print("Testing Track Schematic Tab...")
        page.click("button[data-tab='tab-schematic']")
        time.sleep(1)
        page.screenshot(path="test_browser_schematic.png")
        print("Captured test_browser_schematic.png")

        # 2. Test AI Recommendations Tab & Dynamic Lifecycle
        print("Testing Recommendations Tab...")
        page.click("button[data-tab='tab-recommendations']")
        page.wait_for_selector(".rec-card", timeout=5000)
        time.sleep(1)
        page.screenshot(path="test_browser_recommendations.png")
        print("Captured test_browser_recommendations.png")

        # 3. Test Compound What-If Simulation Sandbox
        print("Testing What-If Compound Simulation...")
        page.click("button[data-tab='tab-whatif']")
        time.sleep(1)

        # Click Preset 1
        page.click("#preset1Btn")
        time.sleep(0.5)

        # Execute simulation
        page.click("#btnRunSimulation")
        page.wait_for_selector("#simResultsContainer:not(.hidden)", timeout=10000)
        time.sleep(1)

        page.screenshot(path="test_browser_whatif_diff.png")
        print("Captured test_browser_whatif_diff.png")

        # 4. Test Ghost Overlay on Marey Chart
        print("Testing Marey Ghost Overlay Toggle...")
        page.click("#btnToggleMareyOverlay")
        time.sleep(1)
        page.screenshot(path="test_browser_marey_overlay.png")
        print("Captured test_browser_marey_overlay.png")

        # 5. Check Console Errors
        print(f"Total page errors: {len(errors)}")
        for e in errors:
            print("ERROR:", e)
        assert len(errors) == 0, f"Found JavaScript errors: {errors}"

        browser.close()
        print("Browser verification completed successfully with 0 errors!")

if __name__ == "__main__":
    run_browser_verification()
