# main.py

import argparse
import logging
import sys
import time

from selenium.common.exceptions import TimeoutException

from aws_cli_utils import AWSCLIUtils
from browser_utils import EC
from browser_utils import BrowserSession
from browser_utils import By
from browser_utils import WebDriverWait
from browser_utils import click_element_by_id
from browser_utils import click_element_by_selector
from browser_utils import dismiss_cookie_banner
from browser_utils import input_text_by_id
from constants import ALLOW_SELECTOR
from constants import CONFIRM_ID
from constants import EMAIL_ID
from constants import MFA_CODE_INPUT_ID
from constants import MFA_DESCRIPTION_ID
from constants import MFA_VERIFY_ID
from constants import PWD_ID
from constants import REQUEST_APPROVED_SELECTOR
from constants import SUBMIT_BUTTON_ID
from credential_manager import CredentialManager

logger = logging.getLogger(__name__)


class AWSSSOLoginAutomator:
    def __init__(self, profile, update_password=False, debug=False):
        self.profile = profile
        self.update_password = update_password
        self.debug = debug
        self.email = None
        self.password = None
        self.sso_url = None
        self.login_process = None

    def get_sso_login_url(self):
        self.sso_url, self.login_process = AWSCLIUtils.get_sso_login_url(self.profile)

    def automate_sso_login(self):
        self.email, self.password = CredentialManager.get_credentials(self.update_password)
        with BrowserSession(debug=self.debug) as browser:
            assert self.sso_url is not None, "SSO URL not found"
            browser.get(self.sso_url)
            logger.info(f"Navigated to URL: {self.sso_url}")

            dismiss_cookie_banner(browser)

            # Define possible states
            states = [
                self.handle_confirmation_code,
                self.handle_mfa,
                self.handle_email_password,
                self.handle_allow_access,
            ]

            # Loop through states until login is complete
            login_complete = False
            while not login_complete:
                for state in states:
                    result = state(browser)
                    if result == "complete":
                        login_complete = True
                        break
                    elif result == "continue":
                        break
                else:
                    # If no state was handled, wait a short time before checking again
                    time.sleep(0.5)

            logger.info("SSO login automated successfully")
            time.sleep(1)

    def handle_confirmation_code(self, browser):
        try:
            logger.info("Checking for confirmation code screen...")
            WebDriverWait(browser, 10).until(EC.presence_of_element_located((By.ID, CONFIRM_ID)))
            logger.info("Confirmation code screen found. Clicking 'Confirm and continue'.")
            click_element_by_id(browser, CONFIRM_ID, "Confirm and Continue")
            # Wait for the element to disappear before returning
            WebDriverWait(browser, 10).until_not(EC.presence_of_element_located((By.ID, CONFIRM_ID)))
            return False  # Return False to move to the next state
        except Exception:
            logger.info("Confirmation code screen not found.")
            return False

    def handle_mfa(self, browser):
        try:
            logger.info("Checking for MFA screen...")
            mfa_description = WebDriverWait(browser, 3).until(
                EC.presence_of_element_located((By.ID, MFA_DESCRIPTION_ID))
            )
            logger.info(f"MFA screen found. Description: {mfa_description.text}")

            mfa_code = input("Enter the code from your authenticator app: ")
            input_text_by_id(browser, MFA_CODE_INPUT_ID, mfa_code, "MFA Code")
            click_element_by_id(browser, MFA_VERIFY_ID, "Verify")
            logger.info("Submitted MFA code.")
            return "continue"
        except TimeoutException:
            logger.info("MFA screen not found. Continuing to next step.")
            return "not_found"
        except Exception as e:
            logger.error(f"Error occurred while handling MFA screen: {str(e)}")
            return "error"

    def handle_email_password(self, browser):
        try:
            WebDriverWait(browser, 3).until(EC.presence_of_element_located((By.ID, EMAIL_ID)))
            logger.info("Email input found. Entering credentials.")
            input_text_by_id(browser, EMAIL_ID, self.email, "Email")
            click_element_by_id(browser, SUBMIT_BUTTON_ID, "Submit Email")

            input_text_by_id(browser, PWD_ID, self.password, "Password")
            click_element_by_id(browser, SUBMIT_BUTTON_ID, "Submit Password")
            return "continue"
        except TimeoutException:
            logger.info("Email/password screen not found.")
            return "not_found"

    def handle_allow_access(self, browser):
        try:
            logger.info("Checking for 'Allow Access' button...")
            WebDriverWait(browser, 10).until(EC.element_to_be_clickable((By.CSS_SELECTOR, ALLOW_SELECTOR)))
            click_element_by_selector(browser, ALLOW_SELECTOR, "Allow Access")
            logger.info("Clicked 'Allow Access' button.")

            # Wait for the "Request approved" message
            logger.info("Waiting for 'Request approved' message...")
            WebDriverWait(browser, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, REQUEST_APPROVED_SELECTOR))
            )
            logger.info("'Request approved' message found. Login process complete.")
            return "complete"
        except Exception as e:
            logger.info(f"'Allow Access' button or 'Request approved' message not found: {str(e)}")
            return "not_found"

    def run(self):
        AWSCLIUtils.check_chrome_chromedriver_compatibility()
        self.get_sso_login_url()
        self.automate_sso_login()
        if self.login_process:
            logger.info("Waiting for 'aws sso login' process to complete...")
            self.login_process.wait()
            logger.info("AWS SSO login process completed successfully.")
        else:
            logger.warning("No AWS SSO login process to wait for.")


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Automate AWS SSO login.")
    parser.add_argument("--profile", default="prod", help="AWS profile to use (default: prod)")
    parser.add_argument("--update-password", action="store_true", help="Update stored password")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    args = parser.parse_args()

    return args


def main():
    args = parse_args()
    if args.debug:
        logger.setLevel(logging.INFO)
    else:
        logger.setLevel(logging.INFO)

    logging.basicConfig(
        level=logger.level,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    automator = AWSSSOLoginAutomator(profile=args.profile, update_password=args.update_password, debug=args.debug)
    try:
        automator.run()
        logger.info(f"AWS SSO login for profile {args.profile} completed successfully.")
        return 0  # Success exit code
    except Exception as e:
        logger.error(f"An error occurred: {str(e)}")
        if args.debug:
            logger.exception("Detailed traceback:")
        return 1  # Failure exit code


if __name__ == "__main__":
    sys.exit(main())
