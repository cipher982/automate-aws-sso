import asyncio
import logging
import re
import time

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def get_sso_login_url():
    logger.info("Executing 'aws sso login --no-browser'")
    try:
        process = await asyncio.create_subprocess_exec(
            "aws",
            "sso",
            "login",
            "--no-browser",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        url_format = r"https://device.sso.[a-z0-9-]+.amazonaws.com/\?user_code=\w+-\w+"

        while True:
            output = await process.stdout.readline()  # type: ignore
            if not output:
                break
            line = output.decode("utf-8").strip()
            logger.info(f"Command output line: {line}")
            url_match = re.search(url_format, line)
            if url_match:
                logger.info(f"Found SSO URL: {url_match.group(0)}")
                process.terminate()
                return url_match.group(0)

        logger.error("Failed to find SSO URL in command output")
        raise ValueError("SSO URL not found")

    except Exception as e:
        logger.error(f"Error executing command: {str(e)}")
        raise


def automate_browser(url):
    logger.info("Starting headless browser to automate SSO login")
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    browser = webdriver.Chrome(options=options)

    try:
        logger.info(f"Attempting to navigate to URL: {url}")
        browser.get(url)
        logger.info(f"Navigated to URL: {url}")
        logger.info(f"Page title: {browser.title}")
        logger.info(f"Current URL: {browser.current_url}")
        browser.save_screenshot("debug_before_clicking_confirm.png")

        # Click 'Confirm and Continue'
        logger.info("Waiting for 'Confirm and Continue' button to be clickable.")
        confirm_button = WebDriverWait(browser, 10).until(
            EC.element_to_be_clickable((By.ID, "cli_verification_btn"))
        )
        confirm_button.click()
        logger.info("Clicked 'Confirm and Continue'")

        # Click 'Allow Access'
        time.sleep(3)  # Wait for 3 seconds
        try:
            allow_access_button = browser.find_element(By.ID, "cli_login_button")
            allow_access_button.click()
        except Exception as e:
            logger.error(f"Error finding or clicking the button: {str(e)}")
            logger.info(f"Page source at error: {browser.page_source}")
            browser.save_screenshot("debug_error.png")
            # Optionally, print or log the current URL if the page has redirected
            logger.info(f"Current URL at error: {browser.current_url}")
        logger.info("Clicked 'Allow Access'")

        logger.info("SSO login automated successfully")
    except Exception as e:
        logger.error(f"Error during automated SSO login: {str(e)}")
        logger.info(f"Page source at error: {browser.page_source}")
        browser.save_screenshot("debug_error.png")
        # Capture browser console logs if possible
        for entry in browser.get_log("browser"):
            logger.info(entry)
        logger.info("Screenshot taken after encountering an error.")
        raise
    finally:
        browser.quit()


async def main():
    try:
        url = await get_sso_login_url()
        await asyncio.to_thread(automate_browser, url)
    except Exception as e:
        logger.error(f"An error occurred: {str(e)}")
        exit(1)


if __name__ == "__main__":
    asyncio.run(main())
