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

    # Try token-based login if token files exist
    token_file = tokenstore / "oauth1_token.json"
    garmin_token_file = tokenstore / "garmin_tokens.json"
    if token_file.exists() or garmin_token_file.exists():
        try:
            client = Garmin()
            client.login(str(tokenstore))
            print("Logged in using cached tokens.")
            return client
        except Exception as e:
            print(f"Token login failed ({e}), falling back to credentials.")

    # Fresh credential login using Garmin() directly
    if not GARMIN_EMAIL or not GARMIN_PASSWORD:
        raise RuntimeError("GARMIN_EMAIL and GARMIN_PASSWORD must be set")

    last_error = None

    for attempt in range(max_retries):
        try:
            client = Garmin(email=GARMIN_EMAIL, password=GARMIN_PASSWORD)
            client.login()
            # Save tokens for future runs
            client.garth.dump(str(tokenstore))
            print("Logged in with credentials and saved tokens.")
            return client
        except GarminConnectTooManyRequestsError as e:
            last_error = e
            sleep_time = base_sleep * (2 ** attempt)
            print(f"Rate limited (attempt {attempt+1}/{max_retries}). Sleeping {sleep_time}s...")
            time.sleep(sleep_time)
        except GarminConnectAuthenticationError as e:
            raise RuntimeError(f"Authentication failed: {e}") from e
        except HTTPError as e:
            if e.response is not None and e.response.status_code == 429:
                last_error = e
                sleep_time = base_sleep * (2 ** attempt)
                print(f"HTTP 429 (attempt {attempt+1}/{max_retries}). Sleeping {sleep_time}s...")
                time.sleep(sleep_time)
            elif e.response is not None and e.response.status_code == 401:
                raise RuntimeError(f"Garmin credentials rejected (401). Check GARMIN_EMAIL and GARMIN_PASSWORD secrets.") from e
            else:
                raise
        except Exception as e:
            raise RuntimeError(f"Unexpected error during Garmin login: {e}") from e

        if attempt < max_retries - 1:
            pass

    raise RuntimeError(f"Failed to authenticate with Garmin after {max_retries} attempts: {last_error}")
