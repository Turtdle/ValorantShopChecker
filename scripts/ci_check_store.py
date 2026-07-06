"""
Unattended store check for the GitHub Action.

Reads a saved Riot session (RIOT_COOKIES secret) and silently mints a fresh
access token from it — no username/password/2FA involved. Posts the result
to a Discord webhook, and writes the (possibly rotated) cookies back out as
a GITHUB_OUTPUT so the workflow can refresh the RIOT_COOKIES secret for next
time.

Required environment variables:
    RIOT_COOKIES         JSON dict of cookie name -> value (from bootstrap_cookies.py)
    DISCORD_WEBHOOK_URL  Discord webhook to post the store to
Optional:
    REGION               Shard/region, defaults to "na"
"""
import json
import os
import sys

import requests

from valorant_auth import (
    AuthError,
    cookies_from_dict,
    cookies_to_dict,
    fetch_store,
    format_store_lines,
    reauth_with_cookies,
)


def post_to_discord(webhook_url: str, content: str) -> None:
    # Discord message content is capped at 2000 chars.
    for i in range(0, len(content), 2000):
        requests.post(webhook_url, json={"content": content[i : i + 2000]}, timeout=15)


def write_github_output(name: str, value: str) -> None:
    output_path = os.environ.get("GITHUB_OUTPUT")
    if not output_path:
        return
    delimiter = "GHADELIM"
    with open(output_path, "a", encoding="utf-8") as f:
        f.write(f"{name}<<{delimiter}\n{value}\n{delimiter}\n")


def main():
    cookies_json = (os.environ.get("RIOT_COOKIES") or "").strip()
    webhook_url = (os.environ.get("DISCORD_WEBHOOK_URL") or "").strip()
    region = os.environ.get("REGION", "na")

    if not webhook_url:
        print("DISCORD_WEBHOOK_URL secret is missing or empty.", file=sys.stderr)
        sys.exit(1)

    if not cookies_json:
        msg = (
            "⚠️ Valorant store check: the RIOT_COOKIES secret is empty. Run "
            "`python scripts/bootstrap_cookies.py` locally, then paste the JSON it "
            "prints into the RIOT_COOKIES repo secret."
        )
        print(msg, file=sys.stderr)
        post_to_discord(webhook_url, msg)
        sys.exit(1)

    try:
        cookies = json.loads(cookies_json)
    except json.JSONDecodeError:
        msg = (
            "⚠️ Valorant store check: the RIOT_COOKIES secret isn't valid JSON. It "
            "must be the exact JSON blob printed by `bootstrap_cookies.py`, e.g. "
            '{"ssid": "...", "tdid": "..."} — with no extra quotes or line breaks.'
        )
        print(msg, file=sys.stderr)
        post_to_discord(webhook_url, msg)
        sys.exit(1)

    session = requests.Session()
    cookies_from_dict(session, cookies)

    access_token = reauth_with_cookies(session)
    if access_token is None:
        post_to_discord(
            webhook_url,
            "⚠️ Valorant store check: the saved Riot session has expired. "
            "Run `python scripts/bootstrap_cookies.py` locally and update the "
            "RIOT_COOKIES secret to fix this.",
        )
        sys.exit(1)

    try:
        store = fetch_store(session, access_token, region)
    except AuthError as e:
        post_to_discord(webhook_url, f"⚠️ Valorant store check failed: {e}")
        sys.exit(1)

    post_to_discord(webhook_url, "\n".join(format_store_lines(store)))

    # Riot may rotate the session cookie on reauth; persist whatever's current.
    write_github_output("cookies", json.dumps(cookies_to_dict(session)))


if __name__ == "__main__":
    main()
