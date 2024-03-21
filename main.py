import argparse
import asyncio
import logging
import re
from contextlib import contextmanager
import time

import keyring
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

# Element IDs and selectors
CONFIRM_ID = "cli_verification_btn"
ALLOW_ID = "cli_login_button"
EMAIL_ID = "i0116"
PWD_ID = "i0118"
MFA_CHECKBOX_ID = "idChkBx_SAOTCC_TD"
MFA_CODE_INPUT_ID = "idTxtBx_SAOTCC_OTC"
MFA_VERIFY_ID = "idSubmit_SAOTCC_Continue"
SUBMIT_BUTTON_ID = "idSIButton9"
DONT_SHOW_AGAIN_CHECKBOX_ID = "KmsiCheckboxField"
YES_BUTTON_ID = "idSIButton9"

MAX_WAIT_TIME = 30


async def get_sso_login_url():
    """Retrieve the SSO login URL using the AWS CLI."""
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
            logger.debug(f"Command output line: {line}")
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


@contextmanager
def browser_session(debug=False):
    """Context manager for handling the browser session."""
    options = webdriver.ChromeOptions()
    if not debug:
        options.add_argument("--headless")
    browser = webdriver.Chrome(options=options)
    try:
        yield browser
    finally:
        browser.quit()


def dismiss_cookie_banner(browser):
    try:
        cookie_banner_button = browser.find_element(By.CSS_SELECTOR, "button[data-id='awsccc-cb-btn-continue']")
        cookie_banner_button.click()
        logger.info("Clicked 'Continue without accepting' button on the cookie banner.")
    except:
        pass


def click_element_by_id(browser, element_id, description):
    """Find and click an element by its ID."""
    logger.info(f"Waiting for '{description}' button to be clickable.")
    element = WebDriverWait(browser, 30).until(EC.element_to_be_clickable((By.ID, element_id)))
    element.click()
    logger.info(f"Clicked '{description}' button.")


def input_text_by_id(browser, element_id, text, description):
    """Find an input element by its ID and enter text."""
    logger.info(f"Waiting for '{description}' input to be visible.")
    element = WebDriverWait(browser, 30).until(EC.visibility_of_element_located((By.ID, element_id)))
    element.send_keys(text)
    logger.info(f"Entered text in '{description}' input.")


def get_credentials():
    """Retrieve the email and password from the keyring or prompt the user."""
    email = keyring.get_password("aws_sso_login", "email")
    password = keyring.get_password("aws_sso_login", "password")

    if not email:
        email = input("Enter your email address: ")
        keyring.set_password("aws_sso_login", "email", email)

    if not password:
        password = input("Enter your password: ")
        keyring.set_password("aws_sso_login", "password", password)

    return email, password


async def automate_sso_login(url, email, password, debug=False):
    with browser_session(debug) as browser:
        browser.get(url)
        logger.info(f"Navigated to URL: {url}")

        dismiss_cookie_banner(browser)
        click_element_by_id(browser, CONFIRM_ID, "Confirm and Continue")

        # Wait for either 'Allow Access' button or email input to appear
        logger.info("Waiting for 'Allow Access' button or email input to appear.")
        element = WebDriverWait(browser, 30).until(
            lambda driver: driver.find_elements(By.ID, ALLOW_ID) or driver.find_elements(By.ID, EMAIL_ID)
        )[0]
        logger.info("Detected 'Allow Access' button or email input.")

        if element.get_attribute("id") == EMAIL_ID:
            dismiss_cookie_banner(browser)
            input_text_by_id(browser, EMAIL_ID, email, "Email")
            click_element_by_id(browser, SUBMIT_BUTTON_ID, "Submit Email")

            dismiss_cookie_banner(browser)
            input_text_by_id(browser, PWD_ID, password, "Password")
            click_element_by_id(browser, SUBMIT_BUTTON_ID, "Submit Password")

            dismiss_cookie_banner(browser)
            click_element_by_id(browser, MFA_CHECKBOX_ID, "Don't ask again for 30 days")

            dismiss_cookie_banner(browser)
            mfa_code = input("Enter your MFA code: ")
            input_text_by_id(browser, MFA_CODE_INPUT_ID, mfa_code, "MFA Code")
            click_element_by_id(browser, MFA_VERIFY_ID, "Submit MFA Code")

            dismiss_cookie_banner(browser)
            click_element_by_id(browser, DONT_SHOW_AGAIN_CHECKBOX_ID, "Don't show this again")
            click_element_by_id(browser, YES_BUTTON_ID, "Yes")

        dismiss_cookie_banner(browser)
        click_element_by_id(browser, ALLOW_ID, "Allow Access")

        logger.info("SSO login automated successfully")
        time.sleep(3)


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Automate AWS SSO login.")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    return parser.parse_args()


async def main():
    args = parse_args()
    if args.debug:
        logger.setLevel(logging.DEBUG)
    try:
        url = await get_sso_login_url()
        email, password = get_credentials()
        await automate_sso_login(url, email, password, args.debug)
    except Exception as e:
        logger.error(f"An error occurred: {str(e)}")
        exit(1)


if __name__ == "__main__":
    asyncio.run(main())
