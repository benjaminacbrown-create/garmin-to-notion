import os
import time
from pathlib import Path

from garminconnect import (
    Garmin,
    GarminConnectAuthenticationError,
    GarminConnectTooManyRequestsError,
)

TOKENSTORE = os.getenv("GARMINTOKENS", ".garminconnect")
GARMIN_EMAIL = os.getenv("GARMIN_EMAIL")
GARMIN_PASSWORD = os.getenv("GARMIN_PASSWORD")


def init_garmin(max_retries=3, base_sleep=120):
    tokenstore = Path(TOKENSTORE)
    tokenstore.mkdir(parents=True, exist_ok=True)
    tokenstore_str = str(tokenstore)

    # garminconnect >= 0.3.0 uses garmin_tokens.json
    token_file = tokenstore / "garmin_tokens.json"

    if token_file.exists():
        try:
            client = Garmin()
            client.login(tokenstore_str)
            print("Logged in using cached tokens.")
            return client
        except Exception as e:
            print(f"Token login failed ({e}), falling back to credentials.")

    # Fresh credential login
    if not GARMIN_EMAIL or not GARMIN_PASSWORD:
        raise RuntimeError(
            "No cached tokens found and GARMIN_EMAIL/GARMIN_PASSWORD not set."
        )

    last_error = None

    for attempt in range(max_retries):
        try:
            client = Garmin(email=GARMIN_EMAIL, password=GARMIN_PASSWORD)
            client.login()
            # Save tokens to tokenstore for future runs
            try:
                client.garth.dump(tokenstore_str)
                print(f"Tokens saved to {tokenstore_str}")
            except Exception as save_err:
                print(f"Warning: Could not save tokens: {save_err}")
            print("Logged in with credentials.")
            return client
        except GarminConnectTooManyRequestsError as e:
            last_error = e
            sleep_time = base_sleep * (2 ** attempt)
            print(f"Rate limited (attempt {attempt+1}/{max_retries}). Sleeping {sleep_time}s...")
            time.sleep(sleep_time)
        except GarminConnectAuthenticationError as e:
            raise RuntimeError(f"Authentication failed: {e}") from e
        except Exception as e:
            err_str = str(e)
            if "429" in err_str:
                last_error = e
                sleep_time = base_sleep * (2 ** attempt)
                print(f"Rate limited (attempt {attempt+1}/{max_retries}). Sleeping {sleep_time}s...")
                time.sleep(sleep_time)
            elif "401" in err_str or "Unauthorized" in err_str:
                raise RuntimeError(
                    f"Garmin credentials rejected (401). "
                    f"Check GARMIN_EMAIL and GARMIN_PASSWORD secrets. Error: {e}"
                ) from e
            else:
                raise RuntimeError(f"Garmin login error: {e}") from e

    raise RuntimeError(f"Failed to authenticate after {max_retries} attempts: {last_error}")
