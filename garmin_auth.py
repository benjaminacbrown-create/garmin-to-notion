import os
import time
from pathlib import Path

from garminconnect import (
    Garmin,
    GarminConnectAuthenticationError,
    GarminConnectTooManyRequestsError,
)
from requests.exceptions import HTTPError

try:
    from garth.exc import GarthHTTPError
except ImportError:
    GarthHTTPError = Exception

TOKENSTORE = os.getenv("GARMINTOKENS", ".garminconnect")
GARMIN_EMAIL = os.getenv("GARMIN_EMAIL")
GARMIN_PASSWORD = os.getenv("GARMIN_PASSWORD")


def init_garmin(max_retries=3, base_sleep=120):
    tokenstore = Path(TOKENSTORE)
    tokenstore.mkdir(parents=True, exist_ok=True)

    # Try token-based login first
    try:
        client = Garmin()
        client.login(str(tokenstore))
        return client
    except (FileNotFoundError, GarthHTTPError, GarminConnectAuthenticationError, Exception):
        pass  # No valid tokens, fall through to fresh credential login

    # Fresh credential login
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

        except (FileNotFoundError, GarthHTTPError) as e:
            # garth couldn't load default token path - this is expected on first run
            # Try to dump whatever session state we have
            try:
                client.garth.dump(str(tokenstore))
                return client
            except Exception:
                last_error = e
                if attempt == max_retries - 1:
                    break

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
