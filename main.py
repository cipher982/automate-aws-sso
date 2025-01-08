# main.py

import argparse
import logging
import sys
import time

from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys

from aws_cli_utils import AWSCLIUtils
from browser_utils import EC
from browser_utils import BrowserSession
from browser_utils import By
from browser_utils import WebDriverWait
from browser_utils import click_element_by_id
from browser_utils import dismiss_cookie_banner
from browser_utils import input_text_by_id
from constants import EMAIL_ID
from constants import MFA_CODE_INPUT_ID
from constants import MFA_DESCRIPTION_ID
from constants import MFA_VERIFY_ID
from constants import PWD_ID
from constants import SUBMIT_BUTTON_ID
from constants import SUCCESS_TEXT_PATTERNS
from constants import SUCCESS_TITLE
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
        self.verification_code = None

    def get_sso_login_url(self):
        """Get the SSO login URL and verification code."""
        final_url, self.verification_code, self.login_process = AWSCLIUtils.get_sso_login_url(self.profile)
        self.sso_url = final_url  # Use the autofill URL when available

    def automate_sso_login(self):
        self.email, self.password = CredentialManager.get_credentials(self.update_password)
        with BrowserSession(debug=self.debug) as browser:
            assert self.sso_url is not None, "SSO URL not found"
            logger.info(f"Navigating to URL: {self.sso_url}")
            browser.get(self.sso_url)
            logger.info(f"Navigated to URL: {self.sso_url}")

            dismiss_cookie_banner(browser)

            # Define possible states with priority order
            states = [
                self.handle_confirmation_code,
                self.handle_mfa,
                self.handle_email_password,
                self.handle_allow_access,
            ]

            # Loop through states until login is complete
            login_complete = False
            consecutive_no_state = 0
            max_consecutive_no_state = 3  # Prevent infinite loops
            last_state = None

            while not login_complete:
                state_handled = False

                # Quickly check each state in order
                for state in states:
                    try:
                        # Skip if we just handled this state and got "continue"
                        if state == last_state:
                            continue

                        logger.info(f"Trying state: {state.__name__}")
                        result = state(browser)

                        if result == "complete":
                            logger.info(f"State {state.__name__} completed login")
                            login_complete = True
                            break
                        elif result == "continue":
                            logger.info(f"State {state.__name__} handled, moving to next state")
                            state_handled = True
                            consecutive_no_state = 0
                            last_state = state
                            break
                        elif result == "not_found":
                            logger.debug(f"State {state.__name__} not applicable")
                            continue

                    except Exception as e:
                        logger.warning(f"Error in state {state.__name__}: {str(e)}")

                # If no state was handled, increment counter
                if not state_handled:
                    consecutive_no_state += 1
                    logger.debug(f"No state handled. Attempt {consecutive_no_state}/{max_consecutive_no_state}")
                    time.sleep(0.1)

                # Prevent getting stuck
                if consecutive_no_state >= max_consecutive_no_state:
                    logger.warning("Multiple consecutive state checks failed. Refreshing page.")
                    browser.refresh()
                    consecutive_no_state = 0
                    last_state = None

            logger.info("SSO login automated successfully")
            time.sleep(1)  # Brief pause to ensure final state is captured

    def handle_confirmation_code(self, browser):
        """Handle the verification code input state."""
        logger.info("State: Handling verification code input")

        try:
            # The code is already filled in via URL, just press Enter
            logger.info("Code auto-filled, submitting...")
            ActionChains(browser).send_keys(Keys.RETURN).perform()
            logger.info("Code submitted")
            return "continue"

        except Exception as e:
            logger.error(f"Failed to handle verification code: {str(e)}")
            return "not_found"

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
            logger.info("Checking for 'Allow Access' button or success state...")

            # Immediately check for success state first
            page_text = browser.page_source.lower()
            page_title = browser.title

            # Quick success check
            for pattern in SUCCESS_TEXT_PATTERNS:
                if pattern.lower() in page_text and page_title == SUCCESS_TITLE:
                    logger.info("Success confirmed with text pattern and title. Login process complete.")
                    return "complete"

            # Look for allow button more aggressively
            try:
                # Try multiple ways to find the button
                buttons = browser.find_elements(By.TAG_NAME, "button")
                allow_buttons = [
                    btn for btn in buttons if any(word in btn.text.lower() for word in ["allow", "grant", "continue"])
                ]

                if allow_buttons:
                    # Click the first matching button
                    allow_button = allow_buttons[0]
                    logger.info(f"Found allow button with text: {allow_button.text}")
                    allow_button.click()
                    return "continue"
            except Exception as e:
                logger.warning(f"Error finding allow button: {str(e)}")

            # If no button found and no success, return not found
            return "not_found"
        except Exception as e:
            logger.error(f"Error in handle_allow_access: {str(e)}")
            return "error"

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
        format="%(levelname)s - %(message)s",
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
