"""
Browser Playwright Example Automation

Starts Chromium headless, opens a local test page,
extracts information, saves screenshot, closes browser.

Uses a local HTML file to avoid external site dependencies.
"""

import json
import os
import sys


def run(context: dict) -> dict:
    """Main entrypoint for browser automation."""
    from playwright.sync_api import sync_playwright

    workspace = os.environ.get("AUTOMATION_WORKSPACE", ".")
    artifacts_path = os.environ.get("AUTOMATION_ARTIFACTS_PATH", os.path.join(workspace, "artifacts"))
    output_path = os.environ.get("AUTOMATION_OUTPUT_PATH", os.path.join(workspace, "output"))
    browser_data = os.environ.get("PLAYWRIGHT_BROWSER_DATA", os.path.join(workspace, "temp", "browser_data"))

    # Create a local test HTML page
    test_html_path = os.path.join(workspace, "temp", "test_page.html")
    os.makedirs(os.path.dirname(test_html_path), exist_ok=True)

    with open(test_html_path, "w", encoding="utf-8") as f:
        f.write("""<!DOCTYPE html>
<html>
<head><title>Biason Automation Test Page</title></head>
<body>
    <h1 id="title">Biason Automation Agent</h1>
    <p id="description">Browser automation test page for Playwright validation.</p>
    <div id="data">
        <span class="item">Item 1</span>
        <span class="item">Item 2</span>
        <span class="item">Item 3</span>
    </div>
    <footer id="timestamp">Generated for testing</footer>
</body>
</html>""")

    print("Starting Playwright browser automation")

    with sync_playwright() as p:
        # Launch Chromium with isolated profile
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"]
        )

        # Create context with separate user data (no cookie sharing)
        browser_context = browser.new_context()
        page = browser_context.new_page()

        # Navigate to local test page
        page.goto(f"file:///{test_html_path.replace(os.sep, '/')}")
        print(f"Navigated to test page")

        # Extract information
        title = page.text_content("#title")
        description = page.text_content("#description")
        items = page.query_selector_all(".item")
        item_texts = [item.text_content() for item in items]

        print(f"Title: {title}")
        print(f"Description: {description}")
        print(f"Items found: {len(item_texts)}")

        # Save screenshot as artifact
        screenshot_path = os.path.join(artifacts_path, "page_screenshot.png")
        page.screenshot(path=screenshot_path, full_page=True)
        print(f"Screenshot saved to {screenshot_path}")

        # Cleanup
        browser_context.close()
        browser.close()
        print("Browser closed")

    result = {
        "title": title,
        "description": description,
        "items": item_texts,
        "screenshot": "page_screenshot.png"
    }

    return result
