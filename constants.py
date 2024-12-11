# constants.py

# Element IDs and selectors
CONFIRM_ID = "cli_verification_btn"
ALLOW_ID = "cli_login_button"
EMAIL_ID = "i0116"
PWD_ID = "i0118"
MFA_DESCRIPTION_ID = "idDiv_SAOTCC_Description"
MFA_CHECKBOX_ID = "idChkBx_SAOTCC_TD"
MFA_CODE_INPUT_ID = "idTxtBx_SAOTCC_OTC"
MFA_VERIFY_ID = "idSubmit_SAOTCC_Continue"
SUBMIT_BUTTON_ID = "idSIButton9"
DONT_SHOW_AGAIN_CHECKBOX_ID = "KmsiCheckboxField"
YES_BUTTON_ID = "idSIButton9"
ALLOW_SELECTOR = "[data-testid='allow-access-button']"
# Update success detection patterns
SUCCESS_TEXT_PATTERNS = [
    "you can close this window",
    "you have successfully logged into aws",
    "request approved",
    "success",
]

# Add selectors for different page states
ALLOW_ACCESS_PAGE_SELECTOR = "form[data-testid='allow-access-form']"
SUCCESS_TITLE = "AWS access portal"

MAX_WAIT_TIME = 30
SERVICE_NAME = "aws_sso_login"
