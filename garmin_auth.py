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

    # Fresh credential login
    if not GARMIN_EMAIL or not GARMIN_PASSWORD:
        raise RuntimeError(
            "No cached tokens found and GARMIN_EMAIL/GARMIN_PASSWORD not set. "
            "Generate tokens locally with: python -c \"import garth; garth.login('EMAIL','PASS'); garth.save('.garminconnect')\" "
            "then store .garminconnect as a GitHub Actions cache or secret."
        )

    last_error = None

    for attempt in range(max_retries):
        try:
            # Configure garth workspace so tokens are saved there
            garth.configure(workspace=str(tokenstore))
            garth.login(GARMIN_EMAIL, GARMIN_PASSWORD)
            # Create client and load the freshly-saved tokens
            client = Garmin()
            client.login(str(tokenstore))
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
                raise RuntimeError(
                    "Garmin SSO rejected credentials (401 Unauthorized). "
                    "Verify GARMIN_EMAIL and GARMIN_PASSWORD secrets are correct. "
                    "If correct, Garmin may be blocking automated logins — "
                    "generate tokens locally and cache them instead."
                ) from e
            else:
                raise
        except Exception as e:
            err_str = str(e)
            if "401" in err_str or "Unauthorized" in err_str:
                raise RuntimeError(
                    "Garmin SSO rejected credentials (401 Unauthorized). "
                    "Verify GARMIN_EMAIL and GARMIN_PASSWORD secrets are correct."
                ) from e
            raise RuntimeError(f"Unexpected error during Garmin login: {e}") from e

    raise RuntimeError(f"Failed to authenticate with Garmin after {max_retries} attempts: {last_error}")
