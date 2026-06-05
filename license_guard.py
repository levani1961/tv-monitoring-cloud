from datetime import date


LICENSE_EXPIRATION_DATE = "2026-06-30"
LICENSE_EXPIRED_MESSAGE = "License expired. Please contact the administrator."


def check_license():
    expiration = date.fromisoformat(LICENSE_EXPIRATION_DATE)
    if date.today() > expiration:
        raise PermissionError(LICENSE_EXPIRED_MESSAGE)
