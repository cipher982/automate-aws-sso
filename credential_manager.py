# credential_manager.py

import getpass
import logging

import keyring

from constants import SERVICE_NAME

logger = logging.getLogger(__name__)


class CredentialManager:
    @staticmethod
    def get_credentials(update_password=False):
        """Retrieve the email and password from the keyring or prompt the user."""
        email = keyring.get_password(SERVICE_NAME, "email")
        password = keyring.get_password(SERVICE_NAME, "password")

        if not email:
            email = input("Enter your email address: ")
            keyring.set_password(SERVICE_NAME, "email", email)

        if not password or update_password:
            password = getpass.getpass("Enter your password: ")
            keyring.set_password(SERVICE_NAME, "password", password)
            logger.info("Password updated successfully.")

        return email, password
