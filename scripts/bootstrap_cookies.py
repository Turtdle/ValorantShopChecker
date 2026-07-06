"""
One-time local login to seed a reusable Riot session for the GitHub Action.

The Action runs unattended, so it can't answer a 2FA prompt. Instead, you log
in once here with username/password (+ 2FA if enabled), which gives Riot's
auth server a chance to set long-lived session cookies on this script's
session. Those cookies alone are enough for the Action to silently mint a
fresh access token on every scheduled run, without ever seeing your password
again.

Run:
    python scripts/bootstrap_cookies.py

Then copy the printed JSON into a repo secret named RIOT_COOKIES:
    gh secret set RIOT_COOKIES

(paste the JSON when prompted, then Ctrl+D / Ctrl+Z+Enter to finish)

If the Action later reports the cookies expired (Riot session cookies aren't
forever), just rerun this and update the secret again.
"""
import getpass
import json

import requests

from valorant_auth import AuthError, login


def main():
    session = requests.Session()
    username = input("Riot username: ").strip()
    password = getpass.getpass("Riot password (hidden): ")

    try:
        login(session, username, password)
    except AuthError as e:
        raise SystemExit(str(e))

    cookies = {c.name: c.value for c in session.cookies if c.domain.endswith("riotgames.com")}
    if not cookies:
        raise SystemExit("Login succeeded but no cookies were captured — nothing to save.")

    print("\nLogin succeeded. Cookie JSON for the RIOT_COOKIES secret:\n")
    print(json.dumps(cookies))
    print(
        "\nSet it with:\n"
        "  gh secret set RIOT_COOKIES\n"
        "(paste the JSON above when prompted, then finish input with Ctrl+D on "
        "Mac/Linux or Ctrl+Z then Enter on Windows)"
    )


if __name__ == "__main__":
    main()
