import argparse
import asyncio
import logging
import os
import re
import subprocess
import time
from contextlib import contextmanager

import keyring
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.chrome.service import Service
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
ALLOW_SELECTOR = "[data-testid='allow-access-button']"

MAX_WAIT_TIME = 30


async def get_sso_login_url(profile: str):
    """Retrieve the SSO login URL using the AWS CLI."""
    assert profile is not None, "Profile must be provided"
    logger.info(f"Executing 'aws sso login --no-browser' with profile '{profile}'")
    try:
        process = await asyncio.create_subprocess_exec(
            "aws",
            "sso",
            "login",
            "--profile",
            profile,
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
    """Context manager for handling the browser session with a custom profile."""
    options = webdriver.ChromeOptions()
    if not debug:
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

    logger.debug(f"Chrome options: {options.arguments}")
    logger.debug(f"Custom profile directory: {custom_profile_dir}")

    service = Service("/opt/homebrew/bin/chromedriver")

    try:
        logger.debug("Attempting to create Chrome browser instance...")
        browser = webdriver.Chrome(service=service, options=options)
        logger.info("Browser session created successfully")
        yield browser
    except Exception as e:
        logger.error(f"Failed to create browser session: {str(e)}")
        raise
    finally:
        if "browser" in locals():
            logger.debug("Closing browser session...")
            browser.quit()
            logger.debug("Browser session closed.")


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
    element = WebDriverWait(browser, 30).until(EC.element_to_be_clickable((By.ID, element_id)))
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
    element = WebDriverWait(browser, 30).until(EC.visibility_of_element_located((By.ID, element_id)))
    element.send_keys(text)
    logger.info(f"Entered text in '{description}' input.")


def get_credentials(update_password=False):
    """Retrieve the email and password from the keyring or prompt the user."""
    email = keyring.get_password("aws_sso_login", "email")
    password = keyring.get_password("aws_sso_login", "password")

    if not email:
        email = input("Enter your email address: ")
        keyring.set_password("aws_sso_login", "email", email)

    if not password or update_password:
        password = input("Enter your password: ")
        keyring.set_password("aws_sso_login", "password", password)
        logger.info("Password updated successfully.")

    return email, password


async def automate_sso_login(url, email, password, debug=False):
    with browser_session(debug) as browser:
        browser.get(url)
        logger.info(f"Navigated to URL: {url}")

        dismiss_cookie_banner(browser)

        # Check for the confirmation code screen first
        try:
            logger.info("Checking for confirmation code screen...")
            WebDriverWait(browser, 10).until(EC.presence_of_element_located((By.ID, CONFIRM_ID)))
            logger.info("Confirmation code screen found. Clicking 'Confirm and continue'.")
            click_element_by_id(browser, CONFIRM_ID, "Confirm and Continue")
        except Exception:
            logger.info("Confirmation code screen not found. Proceeding with login process.")

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

                # Check if MFA is required
                try:
                    WebDriverWait(browser, 10).until(EC.presence_of_element_located((By.ID, MFA_CHECKBOX_ID)))
                    logger.info("MFA required. Proceeding with MFA process.")

                    dismiss_cookie_banner(browser)
                    click_element_by_id(browser, MFA_CHECKBOX_ID, "Don't ask again for 30 days")

                    dismiss_cookie_banner(browser)
                    mfa_code = input("Enter your MFA code: ")
                    input_text_by_id(browser, MFA_CODE_INPUT_ID, mfa_code, "MFA Code")
                    click_element_by_id(browser, MFA_VERIFY_ID, "Submit MFA Code")

                    dismiss_cookie_banner(browser)
                    click_element_by_id(browser, DONT_SHOW_AGAIN_CHECKBOX_ID, "Don't show this again")
                    click_element_by_id(browser, YES_BUTTON_ID, "Yes")
                except Exception:
                    logger.info("MFA not required or already completed.")

        # Wait for the "Allow Access" button
        try:
            logger.info("Waiting for 'Allow Access' button...")
            WebDriverWait(browser, MAX_WAIT_TIME).until(EC.element_to_be_clickable((By.CSS_SELECTOR, ALLOW_SELECTOR)))
            click_element_by_selector(browser, ALLOW_SELECTOR, "Allow Access")
            logger.info("Clicked 'Allow Access' button.")
        except Exception as e:
            logger.error(f"Failed to find or click 'Allow Access' button: {str(e)}")
            raise

        logger.info("SSO login automated successfully")
        time.sleep(1)


def get_chrome_version():
    try:
        output = subprocess.check_output(["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "--version"])
        return output.decode().strip().split()[-1]
    except Exception as e:
        logger.error(f"Failed to get Chrome version: {str(e)}")
        return None


def get_chromedriver_version():
    try:
        output = subprocess.check_output(["/opt/homebrew/bin/chromedriver", "--version"])
        return output.decode().strip().split()[1]
    except Exception as e:
        logger.error(f"Failed to get ChromeDriver version: {str(e)}")
        return None


def check_chrome_chromedriver_compatibility():
    chrome_version = get_chrome_version()
    chromedriver_version = get_chromedriver_version()

    if chrome_version and chromedriver_version:
        chrome_major = chrome_version.split(".")[0]
        chromedriver_major = chromedriver_version.split(".")[0]

        if chrome_major != chromedriver_major:
            logger.warning(
                f"Chrome version ({chrome_version}) and ChromeDriver version ({chromedriver_version}) may be incompatible."
            )
            logger.warning("Please update ChromeDriver to match your Chrome version.")
        else:
            logger.info("Chrome and ChromeDriver versions appear to be compatible.")
    else:
        logger.warning("Unable to check Chrome and ChromeDriver compatibility.")


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Automate AWS SSO login.")
    parser.add_argument("--profile", default="prod", help="AWS profile to use (default: prod)")
    parser.add_argument("--update-password", action="store_true", help="Update stored password")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    return parser.parse_args()


async def main():
    args = parse_args()
    if args.debug:
        logger.setLevel(logging.DEBUG)

    check_chrome_chromedriver_compatibility()

    try:
        url = await get_sso_login_url(args.profile)
        email, password = get_credentials(args.update_password)
        await automate_sso_login(url, email, password, args.debug)
    except Exception as e:
        logger.error(f"An error occurred in main: {str(e)}")
        if args.debug:
            logger.exception("Detailed traceback:")
        exit(1)


if __name__ == "__main__":
    asyncio.run(main())
