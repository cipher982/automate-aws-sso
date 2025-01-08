# aws_cli_utils.py

import logging
import re
import subprocess

logger = logging.getLogger(__name__)


class AWSCLIUtils:
    @staticmethod
    def get_sso_login_url(profile):
        """Retrieve the SSO login URL using the AWS CLI."""
        assert profile is not None, "Profile must be provided"
        logger.info(f"Executing 'aws sso login --no-browser' with profile '{profile}'")
        try:
            command = [
                "aws",
                "sso",
                "login",
                "--profile",
                profile,
                "--no-browser",
            ]
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            # More flexible URL matching
            url_patterns = [
                r"https://.*awsapps\.com/start/#/device",
                r"https://device\.sso\.[a-z0-9-]+\.amazonaws\.com/\?user_code=\w+-\w+",
            ]

            sso_url = None
            if process.stdout:
                for line in process.stdout:
                    logger.info(f"Command output line: {line.strip()}")
                    for pattern in url_patterns:
                        url_match = re.search(pattern, line)
                        if url_match:
                            sso_url = url_match.group(0)
                            logger.info(f"Found SSO URL: {sso_url}")
                            break
                    if sso_url:
                        break

            if not sso_url:
                process.terminate()
                logger.error("Failed to find SSO URL in command output")
                raise ValueError("SSO URL not found")

            return sso_url, process

        except Exception as e:
            logger.error(f"Error executing command: {str(e)}")
            raise

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
