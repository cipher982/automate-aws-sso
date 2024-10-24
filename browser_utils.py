# browser_utils.py

import logging
import os

from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
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
        if not self.debug:
            options.add_argument("--headless")

        # Create a custom Chrome profile directory
        custom_profile_dir = os.path.expanduser("~/aws_sso_automation_profile")
        os.makedirs(custom_profile_dir, exist_ok=True)

        options.add_argument(f"user-data-dir={custom_profile_dir}")
        options.add_argument("profile-directory=Default")

        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)

        logger.info(f"Chrome options: {options.arguments}")
        logger.info(f"Custom profile directory: {custom_profile_dir}")

        service = Service("/opt/homebrew/bin/chromedriver")

        try:
            logger.info("Attempting to create Chrome browser instance...")
            # Replace the hardcoded service with ChromeDriverManager
            service = ChromeService(ChromeDriverManager().install())
            self.browser = webdriver.Chrome(service=service, options=options)
            logger.info("Browser session created successfully")
            return self.browser
        except Exception as e:
            logger.error(f"Failed to create browser session: {str(e)}")
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
