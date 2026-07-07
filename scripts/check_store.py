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
    competitive_updates,
    compute_match_stats,
    extract_access_token,
    format_rank_lines,
    format_season_stats_lines,
    format_store_lines,
    game_headers,
    get_current_act,
    login,
    paged_competitive_matches,
    store_front,
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

        # One auth handshake, reused across every game endpoint below.
        headers, puuid = game_headers(session, access_token)
        store = store_front(session, headers, puuid, args.region)

        # Recent updates drive the current-rank + last-5-matches readout.
        updates = competitive_updates(session, headers, puuid, args.region, count=5)
        _, act_start = get_current_act()
        matches = paged_competitive_matches(session, headers, puuid, args.region, act_start)
        print(f"\nComputing winrate + K/D over all {len(matches)} ranked games this act...")
        stats = compute_match_stats(
            session, headers, puuid, args.region, matches, progress=True
        )
    except AuthError as e:
        raise SystemExit(str(e))

    print()
    print("\n".join(format_store_lines(store)))
    print()
    print("\n".join(format_rank_lines(updates)))
    print()
    print("\n".join(format_season_stats_lines(stats)))


if __name__ == "__main__":
    main()
