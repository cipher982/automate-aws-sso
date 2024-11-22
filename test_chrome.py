import os

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager


def main(headless=False):
    options = Options()
    options.add_argument("--no-sandbox")

    # Create persistent profile directory
    profile_dir = os.path.expanduser("~/aws_sso_profile")
    os.makedirs(profile_dir, exist_ok=True)

    # Add profile directory with proper formatting
    options.add_argument(f"user-data-dir={profile_dir}")  # Note: removed the -- prefix

    if headless:
        options.add_argument("--headless")

    print("Starting Chrome...")
    driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=options)

    print("Opening google.com...")
    driver.get("https://www.google.com")

    if not headless:
        input("Press Enter to close browser...")
    driver.quit()


if __name__ == "__main__":
    main(headless=False)
