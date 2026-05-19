import os
import time
from pathlib import Path

from garminconnect import (
    Garmin,
    GarminConnectAuthenticationError,
    GarminConnectTooManyRequestsError,
)
from requests.exceptions import HTTPError

TOKENSTORE = os.getenv("GARMINTOKENS", ".garminconnect")
GARMIN_EMAIL = os.getenv("GARMIN_EMAIL")
GARMIN_PASSWORD = os.getenv("GARMIN_PASSWORD")


def _try_token_login(tokenstore):
    """Attempt to login using saved tokens. Returns client or raises."""
    client = Garmin()
    client.login(str(tokenstore))
    return client


def _fresh_login(tokenstore, max_retries=3, base_sleep=120):
    """Login with email/password credentials and save tokens."""
    if not GARMIN_EMAIL or not GARMIN_PASSWORD:
        raise RuntimeError("GARMIN_EMAIL and GARMIN_PASSWORD must be set")

    last_error = None

    for attempt in range(max_retries):
        try:
            client = Garmin(
                email=GARMIN_EMAIL,
                password=GARMIN_PASSWORD,
                is_cn=False,
            )
            client.login()
            client.garth.dump(str(tokenstore))
            return client

        except GarminConnectTooManyRequestsError as e:
            last_error = e
            if attempt == max_retries - 1:
                break
            time.sleep(base_sleep * (2 ** attempt))

        except HTTPError as e:
            if "429" in str(e):
                last_error = e
                if attempt == max_retries - 1:
                    break
                time.sleep(base_sleep * (2 ** attempt))
            else:
                raise

    raise RuntimeError(
        f"Failed to authenticate with Garmin after {max_retries} attempts"
    ) from last_error


def init_garmin(max_retries=3, base_sleep=120):
    tokenstore = Path(TOKENSTORE)
    tokenstore.mkdir(parents=True, exist_ok=True)

    # Try token-based login first
    try:
        return _try_token_login(tokenstore)
    except (FileNotFoundError, GarminConnectAuthenticationError, Exception):
        pass  # Fall through to fresh credential login

    # Fall back to fresh credential login
    return _fresh_login(tokenstore, max_retries=max_retries, base_sleep=base_sleep)
