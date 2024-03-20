import argparse
import asyncio
import logging
import re

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait
from selenium.common.exceptions import NoSuchElementException, ElementClickInterceptedException


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


def find_element_if_present(driver, by, locator):
    elements = driver.find_elements(by, locator)
    return elements[0] if elements else False


def parse_args():
    parser = argparse.ArgumentParser(description="Automate AWS SSO login.")
    parser.add_argument("--email", required=True, help="Email address for SSO login")
    return parser.parse_args()


def automate_browser(url, email):
    logger.info("Starting headless browser to automate SSO login")
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    browser = webdriver.Chrome(options=options)

    try:
        browser.get(url)
        logger.info(f"Navigated to URL: {url}")

        # Click 'Confirm and Continue'
        logger.info("Waiting for 'Confirm and Continue' button to be clickable.")
        confirm_button = WebDriverWait(browser, 10).until(EC.element_to_be_clickable((By.ID, "cli_verification_btn")))
        confirm_button.click()
        logger.info("Clicked 'Confirm and Continue'")

        # Wait for either 'Allow Access' button or email input to appear
        logger.info("Waiting for 'Allow Access' button or email input to appear.")
        allow_button_id = "cli_login_button"
        email_input_id = "i0116"

        # Wait for either element to appear
        element = WebDriverWait(browser, 30).until(
            lambda driver: find_element_if_present(driver, By.ID, allow_button_id)
            or find_element_if_present(driver, By.ID, email_input_id)
        )
        logger.info("Detected 'Allow Access' button or email input.")

        # Start handling the found element
        if element.get_attribute("id") == email_input_id:
            logger.info("Email login detected. Inputting email address.")
            element.send_keys(email)
            submit_button = browser.find_element(By.ID, "idSIButton9")
            submit_button.click()
            logger.info("Submitted email login.")
        else:
            logger.info("Allow Access button detected. Clicking.")
            allow_button = browser.find_element(By.ID, allow_button_id)
            allow_button.click()
            logger.info("Clicked Allow Access button.")

        logger.info("SSO login automated successfully")
    except Exception as e:
        logger.error(f"Error during automated SSO login: {str(e)}")
        browser.save_screenshot("debug_error.png")
        raise
    finally:
        browser.quit()


async def main():
    args = parse_args()
    try:
        url = await get_sso_login_url()
        await asyncio.to_thread(automate_browser, url, args.email)
    except Exception as e:
        logger.error(f"An error occurred: {str(e)}")
        exit(1)


if __name__ == "__main__":
    asyncio.run(main())
