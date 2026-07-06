"""
One-time setup to seed a reusable Riot session for the GitHub Action.

The Action runs unattended, so it can't type a password or answer a 2FA
prompt. Instead it reuses your Riot SSO session cookie (`ssid`), which is
long-lived and lets the Action silently mint a fresh access token on every
run. This script takes that cookie, verifies it actually works, and prints
the JSON to store in the RIOT_COOKIES secret.

HOW TO GET YOUR ssid COOKIE
---------------------------
1. In a browser, open this URL and log in if prompted:
   https://auth.riotgames.com/authorize?redirect_uri=https%3A%2F%2Fplayvalorant.com%2Fopt_in&client_id=play-valorant-web-prod&response_type=token%20id_token&nonce=1&scope=account%20openid
2. Once you land on the playvalorant.com/opt_in page, open DevTools (F12).
3. Go to:  Application (Chrome) / Storage (Firefox)  ->  Cookies
   ->  https://auth.riotgames.com
4. Find the cookie named `ssid` and copy its full Value (it's long).

Then run this script and paste that value when prompted.

Run:
    python scripts/bootstrap_cookies.py

If the Action later reports the session expired (ssid cookies aren't forever),
just rerun this with a fresh ssid and update the RIOT_COOKIES secret.
"""
import json

import requests

from valorant_auth import cookies_from_dict, cookies_to_dict, fetch_store, reauth_with_cookies


def main():
    print(__doc__)
    ssid = input("Paste your ssid cookie value: ").strip()
    if not ssid:
        raise SystemExit("No ssid provided — nothing to do.")
    # Some people copy the whole "ssid=..." pair; be forgiving.
    if ssid.lower().startswith("ssid="):
        ssid = ssid.split("=", 1)[1].strip()

    session = requests.Session()
    cookies_from_dict(session, {"ssid": ssid})

    print("\nVerifying the cookie by minting a fresh access token...")
    access_token = reauth_with_cookies(session)
    if access_token is None:
        raise SystemExit(
            "That ssid cookie didn't work — Riot didn't return a token. Make sure you "
            "copied the full value of the `ssid` cookie from auth.riotgames.com (not a "
            "different cookie), and that you were logged in when you copied it."
        )

    # Sanity check that it can actually reach the store, and surface region issues early.
    region = input("Confirm your region [na]: ").strip() or "na"
    try:
        store = fetch_store(session, access_token, region)
    except Exception as e:  # noqa: BLE001 - surface any failure to the user
        raise SystemExit(f"Cookie authenticated, but the store fetch failed: {e}")

    if "SkinsPanelLayout" not in store:
        raise SystemExit(f"Unexpected store response — check your region. Got: {store}")

    cookies = cookies_to_dict(session)
    print("\n✅ Success — the session works. JSON for your RIOT_COOKIES secret:\n")
    print(json.dumps(cookies))
    print(
        "\nPaste that whole line into the RIOT_COOKIES repo secret at:\n"
        "  Settings -> Secrets and variables -> Actions -> RIOT_COOKIES\n"
        f"(Also make sure the workflow's REGION matches: {region})"
    )


if __name__ == "__main__":
    main()
