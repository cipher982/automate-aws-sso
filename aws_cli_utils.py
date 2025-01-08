# aws_cli_utils.py

import logging
import subprocess
import threading

logger = logging.getLogger(__name__)


class AWSCLIUtils:
    @staticmethod
    def get_sso_login_url(profile):
        """Execute AWS SSO login command and extract the login URL and verification code."""
        logger.info(f"Executing 'aws sso login --no-browser' with profile '{profile}'")

        process = subprocess.Popen(
            ["aws", "sso", "login", "--no-browser", "--profile", profile],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )

        sso_url = None
        verification_code = None
        autofill_url = None

        # Start a thread to read stderr to prevent blocking
        def read_stderr():
            for line in process.stderr:
                if line.strip():
                    logger.debug(f"AWS CLI stderr: {line.strip()}")

        stderr_thread = threading.Thread(target=read_stderr)
        stderr_thread.daemon = True
        stderr_thread.start()

        # Read stdout with timeout
        while True:
            line = process.stdout.readline()
            if not line:
                break

            line = line.strip()
            if not line:
                continue

            logger.info(f"Command output line: {line}")

            # Look for the autofill URL first
            if "user_code=" in line:
                autofill_url = line
                logger.info(f"Found autofill URL: {autofill_url}")
                # We found what we need, kill the process
                process.terminate()
                break

            # Fallback to regular URL and code
            elif "https://" in line:
                sso_url = line
                logger.info(f"Found SSO URL: {sso_url}")
            elif any(c.isalpha() and c.isupper() for c in line) and "-" in line:
                verification_code = line
                logger.info(f"Found verification code: {verification_code}")

        # Return the autofill URL if we found it, otherwise the regular URL
        return (autofill_url if autofill_url else sso_url), verification_code, None

    @staticmethod
    def get_chrome_version():
        try:
            output = subprocess.check_output(["google-chrome", "--version"])
            return output.decode().strip().split()[-1]
        except Exception as e:
            logger.error(f"Failed to get Chrome version: {str(e)}")
            return None

    @staticmethod
    def get_chromedriver_version():
        try:
            output = subprocess.check_output(["chromedriver", "--version"])
            return output.decode().strip().split()[1]
        except Exception as e:
            logger.error(f"Failed to get ChromeDriver version: {str(e)}")
            return None

    @staticmethod
    def check_chrome_chromedriver_compatibility():
        chrome_version = AWSCLIUtils.get_chrome_version()
        chromedriver_version = AWSCLIUtils.get_chromedriver_version()

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
