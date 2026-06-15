"""
[DOMAIN: SALESFORCE]
Salesforce login helper for Playwright retest scripts.

Handles Lightning Experience login flow.
Credentials loaded from .env — never hardcoded in scripts.

Usage:
    from retest.shared.sf_login import login

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        login(page)
        page.goto("https://...")
"""

import logging
import os

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError

logger = logging.getLogger(__name__)

# Salesforce Lightning login URL pattern
_SF_LOGIN_PATH = "/lightning/login"


def login(page: Page) -> None:
    """
    Log in to Salesforce Lightning Experience.

    Reads credentials from environment variables:
        SF_BASE_URL   — e.g. https://brave-goat-4r7ip-dev-ed.trailblaze.lightning.force.com
        SF_USERNAME   — e.g. marcin00001a@brave-goat-4r7ip.com
        SF_PASSWORD   — Salesforce password

    Args:
        page: Playwright Page object (browser must be open)

    Raises:
        EnvironmentError: if required env vars are missing
        PlaywrightTimeoutError: if login page doesn't load or login fails
    """
    base_url = os.getenv("SF_BASE_URL", "").rstrip("/")
    username = os.getenv("SF_USERNAME", "")
    password = os.getenv("SF_PASSWORD", "")

    if not all([base_url, username, password]):
        missing = [k for k, v in {
            "SF_BASE_URL": base_url,
            "SF_USERNAME": username,
            "SF_PASSWORD": password,
        }.items() if not v]
        raise EnvironmentError(
            f"Missing Salesforce credentials in .env: {', '.join(missing)}\n"
            f"Add SF_BASE_URL, SF_USERNAME, SF_PASSWORD to your .env file."
        )

    login_url = f"{base_url}{_SF_LOGIN_PATH}"
    logger.info(f"[sf_login] Navigating to: {login_url}")
    page.goto(login_url)

    # Salesforce login form — standard Lightning selectors
    page.wait_for_selector("input#username", timeout=15_000)
    page.fill("input#username", username)
    page.fill("input#password", password)
    page.click("input#Login")

    # Wait for Lightning Experience to load — URL changes after successful login
    try:
        page.wait_for_url(f"{base_url}/**", timeout=20_000)
        logger.info(f"[sf_login] Logged in as: {username}")
    except PlaywrightTimeoutError:
        # Check for error message on login page
        error = page.query_selector(".loginError, #error")
        if error:
            raise PlaywrightTimeoutError(
                f"Salesforce login failed for {username}. "
                f"Error: {error.inner_text()}"
            )
        raise