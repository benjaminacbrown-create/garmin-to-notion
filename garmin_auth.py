import os
import time
from pathlib import Path

import garth
from garminconnect import (
    Garmin,
    GarminConnectAuthenticationError,
    GarminConnectTooManyRequestsError,
)
from requests.exceptions import HTTPError

TOKENSTORE = os.getenv("GARMINTOKENS", ".garminconnect")
GARMIN_EMAIL = os.getenv("GARMIN_EMAIL")
GARMIN_PASSWORD = os.getenv("GARMIN_PASSWORD")


def init_garmin(max_retries=3, base_sleep=120):
    tokenstore = Path(TOKENSTORE)
    tokenstore.mkdir(parents=True, exist_ok=True)

    # Try token-based login if token file exists
    token_file = tokenstore / "oauth1_token.json"
    garmin_token_file = tokenstore / "garmin_tokens.json"
    if token_file.exists() or garmin_token_file.exists():
        try:
            client = Garmin()
            client.login(str(tokenstore))
            return client
        except Exception:
            pass  # Tokens invalid/expired, fall through to fresh login

    # Fresh credential login using garth directly to bypass garminconnect wrapper
    if not GARMIN_EMAIL or not GARMIN_PASSWORD:
        raise RuntimeError("GARMIN_EMAIL and GARMIN_PASSWORD must be set")

    last_error = None

    for attempt in range(max_retries):
        try:
            # Use garth to perform SSO login directly
            garth.login(GARMIN_EMAIL, GARMIN_PASSWORD)
            garth.save(str(tokenstore))

            # Now create a Garmin client and load the just-saved tokens
            client = Garmin()
            client.login(str(tokenstore))
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

        except Exception as e:
            last_error = e
            if attempt == max_retries - 1:
                break
            time.sleep(base_sleep)

    raise RuntimeError(
        f"Failed to authenticate with Garmin after {max_retries} attempts"
    ) from last_error
