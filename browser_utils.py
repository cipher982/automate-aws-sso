# browser_utils.py

import logging
import os
import time

from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

from constants import MAX_WAIT_TIME

logger = logging.getLogger(__name__)


class BrowserSession:
    def __init__(self, debug=False):
        self.debug = debug
        self.browser = None

    def __enter__(self):
        options = Options()
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_experimental_option("excludeSwitches", ["enable-logging"])

        # Create persistent profile directory
        profile_dir = os.path.expanduser("~/aws_sso_profile")
        os.makedirs(profile_dir, exist_ok=True)
        options.add_argument(f"user-data-dir={profile_dir}")

        try:
            logger.info("Attempting to create Chrome browser instance...")

            # Set Chrome binary location for macOS
            chrome_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
            if os.path.exists(chrome_path):
                logger.info(f"Found Chrome binary at: {chrome_path}")
                options.binary_location = chrome_path

            # Initialize ChromeDriver
            service = ChromeService(ChromeDriverManager().install())
            self.browser = webdriver.Chrome(service=service, options=options)
            logger.info("Browser session created successfully")
            return self.browser

        except Exception as e:
            logger.error(f"Failed to create browser session: {str(e)}", exc_info=True)
            raise

    def __exit__(self, exc_type, exc_value, traceback):
        if self.browser:
            logger.info("Closing browser session...")
            self.browser.quit()
            logger.info("Browser session closed.")


def dismiss_cookie_banner(browser):
    try:
        cookie_banner_button = browser.find_element(By.CSS_SELECTOR, "button[data-id='awsccc-cb-btn-continue']")
        cookie_banner_button.click()
        logger.info("Clicked 'Continue without accepting' button on the cookie banner.")
    except NoSuchElementException:
        logger.info("No cookie banner found; proceeding without dismissing.")
    except Exception as e:
        logger.warning(f"Unexpected error while dismissing cookie banner: {e}")


def click_element_by_id(browser, element_id, description):
    """Find and click an element by its ID."""
    logger.info(f"Waiting for '{description}' button to be clickable.")
    element = WebDriverWait(browser, MAX_WAIT_TIME).until(EC.element_to_be_clickable((By.ID, element_id)))
    element.click()
    logger.info(f"Clicked '{description}' button.")


def click_element_by_selector(browser, selector, description):
    """Find and click an element by its CSS selector."""
    logger.info(f"Waiting for '{description}' button to be clickable.")
    element = WebDriverWait(browser, MAX_WAIT_TIME).until(EC.element_to_be_clickable((By.CSS_SELECTOR, selector)))
    element.click()
    logger.info(f"Clicked '{description}' button.")


def input_text_by_id(browser, element_id, text, description):
    """Find an input element by its ID and enter text."""
    logger.info(f"Waiting for '{description}' input to be visible.")
    element = WebDriverWait(browser, MAX_WAIT_TIME).until(EC.visibility_of_element_located((By.ID, element_id)))
    element.send_keys(text)
    logger.info(f"Entered text in '{description}' input.")


def wait_for_page_load(browser, timeout=10):
    """Wait for the page to complete loading."""

    def page_has_loaded(driver):
        return driver.execute_script("return document.readyState") == "complete"

    try:
        WebDriverWait(browser, timeout).until(page_has_loaded)
        return True
    except Exception as e:
        logger.warning(f"Page load wait timed out: {str(e)}")
        return False


def smart_wait(browser, min_wait=0.1, max_wait=2.0, timeout=10):
    """
    Smart waiting strategy that combines page load detection with dynamic polling.
    Returns True if page is ready, False if timeout occurred.
    """
    start_time = time.time()
    current_wait = min_wait

    while time.time() - start_time < timeout:
        if wait_for_page_load(browser, timeout=1):
            return True

        # Exponential backoff with max limit
        time.sleep(current_wait)
        current_wait = min(max_wait, current_wait * 1.5)

    return False


if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")

    # Test the browser session with debug mode (non-headless)
    with BrowserSession(debug=True) as browser:
        # Navigate to a test page
        browser.get("https://aws.amazon.com")

        # Test cookie banner dismissal
        dismiss_cookie_banner(browser)

        # Wait for user to verify
        input("Press Enter to close the browser...")
