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


def init_garmin(max_retries=3, base_sleep=120):
    tokenstore = Path(TOKENSTORE)
    tokenstore.mkdir(parents=True, exist_ok=True)

    # Check if token files exist before trying to load them
    token_file = tokenstore / "oauth1_token.json"
    if token_file.exists():
        try:
            client = Garmin()
            client.login(str(tokenstore))
            return client
        except Exception:
            pass  # Fall through to fresh login

    # No saved tokens - do a fresh username/password login
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
            client.login()  # fresh login, no tokenstore arg
            client.garth.dump(str(tokenstore))  # save tokens for next run
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
