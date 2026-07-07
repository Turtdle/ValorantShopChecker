"""
Check your own Valorant store from the command line.

Run this yourself in a local terminal:
    python scripts/check_store.py

You'll be asked to either:
  1) Go to the URL below in your browser (log in if prompted), then paste the
     redirect URL you land on (the one starting with
     https://playvalorant.com/opt_in#access_token=...):

     https://auth.riotgames.com/authorize?redirect_uri=https%3A%2F%2Fplayvalorant.com%2Fopt_in&client_id=play-valorant-web-prod&response_type=token%20id_token&nonce=1&scope=account%20openid

  2) Log in with username/password directly (hidden input via getpass, plus
     a 2FA prompt if needed).

Nothing is sent anywhere except Riot's own auth servers and valorant-api.com
(used only to translate item IDs into readable names).

Region defaults to "na" — pass a different one if needed, e.g.:
    python scripts/check_store.py --region eu
"""
import argparse
import getpass

import requests

from valorant_auth import (
    AUTHORIZE_URL,
    AuthError,
    extract_access_token,
    fetch_competitive,
    fetch_store,
    format_rank_lines,
    format_store_lines,
    login,
)


def main():
    parser = argparse.ArgumentParser(description="Check your Valorant store.")
    parser.add_argument("--region", default="na", help="Shard/region, e.g. na, eu, ap, kr")
    parser.add_argument(
        "--url",
        help="Paste the full playvalorant.com/opt_in redirect URL here to skip the prompt.",
    )
    args = parser.parse_args()

    session = requests.Session()

    try:
        if args.url:
            access_token = extract_access_token(args.url)
        else:
            print(f"Go to this URL in your browser, log in, then copy the address bar URL you land on:\n{AUTHORIZE_URL}\n")
            pasted = input(
                "Paste that redirect URL here (or press Enter to log in with "
                "username/password instead): "
            ).strip()
            if pasted:
                access_token = extract_access_token(pasted)
            else:
                username = input("Riot username: ").strip()
                password = getpass.getpass("Riot password (hidden): ")
                access_token = login(session, username, password)

        store = fetch_store(session, access_token, args.region)
        comp = fetch_competitive(session, access_token, args.region)
    except AuthError as e:
        raise SystemExit(str(e))

    print()
    print("\n".join(format_store_lines(store)))
    print()
    print("\n".join(format_rank_lines(comp)))


if __name__ == "__main__":
    main()
