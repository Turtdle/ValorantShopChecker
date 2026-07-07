"""Shared helpers for Riot RSO auth and the Valorant store endpoint.

Used by check_store.py (interactive), bootstrap_cookies.py (one-time local
login to seed a reusable session), and ci_check_store.py (unattended,
cookie-based refresh for the GitHub Action).
"""
import re
from urllib.parse import parse_qs, urlparse

import requests

AUTH_URL = "https://auth.riotgames.com/api/v1/authorization"
AUTHORIZE_URL = (
    "https://auth.riotgames.com/authorize"
    "?redirect_uri=https%3A%2F%2Fplayvalorant.com%2Fopt_in"
    "&client_id=play-valorant-web-prod"
    "&response_type=token%20id_token"
    "&nonce=1&scope=account%20openid"
)
ENTITLEMENTS_URL = "https://entitlements.auth.riotgames.com/api/token/v1"
USERINFO_URL = "https://auth.riotgames.com/userinfo"
VERSION_URL = "https://valorant-api.com/v1/version"
SKINLEVELS_URL = "https://valorant-api.com/v1/weapons/skinlevels"
COMPETITIVE_TIERS_URL = "https://valorant-api.com/v1/competitivetiers"
MAPS_URL = "https://valorant-api.com/v1/maps"
CLIENT_PLATFORM = (
    "ew0KCSJwbGF0Zm9ybVR5cGUiOiAiUEMiLA0KCSJwbGF0Zm9ybU9TIjogIldpbmRvd3MiLA0KCSJwbGF0Zm9ybU9T"
    "VmVyc2lvbiI6ICIxMC4wLjE5MDQyLjEuMjU2LjY0Yml0IiwNCgkicGxhdGZvcm1DaGlwc2V0IjogIlVua25vd24i"
    "DQp9"
)

TOKEN_PATTERN = re.compile(
    r"access_token=((?:[a-zA-Z]|\d|\.|-|_)*).*id_token=((?:[a-zA-Z]|\d|\.|-|_)*).*expires_in=(\d*)"
)


class AuthError(Exception):
    pass


def login(session: requests.Session, username: str, password: str, code_prompt=input) -> str:
    """Full username/password (+ 2FA) login. Returns an access_token.

    code_prompt lets callers override how a 2FA code is obtained (defaults to
    a blocking input() — not usable from an unattended CI run).
    """
    session.post(
        AUTH_URL,
        json={
            "client_id": "play-valorant-web-prod",
            "nonce": "1",
            "redirect_uri": "https://playvalorant.com/opt_in",
            "response_type": "token id_token",
        },
    )

    resp = session.put(
        AUTH_URL, json={"type": "auth", "username": username, "password": password}
    ).json()

    if resp.get("type") == "multifactor":
        method = resp["multifactor"].get("method", "email")
        code = code_prompt(f"Enter your {method} 2FA code: ").strip()
        resp = session.put(
            AUTH_URL, json={"type": "multifactor", "code": code, "rememberDevice": False}
        ).json()

    if "error" in resp:
        error = resp["error"]
        hint = {
            "auth_failure": "the username or password is wrong (use your Riot login "
            "email/username, not your in-game name).",
            "rate_limited": "too many attempts — wait a while before retrying.",
        }.get(error, "Riot rejected the login (possibly a captcha challenge this script can't solve).")
        raise AuthError(f"Login failed: {error} — {hint}")
    if resp.get("type") != "response":
        raise AuthError(f"Login failed, unexpected response: {resp}")

    uri = resp["response"]["parameters"]["uri"]
    match = TOKEN_PATTERN.findall(uri)
    if not match:
        raise AuthError(f"Could not parse tokens from response: {uri}")
    return match[0][0]  # access_token


def extract_access_token(url: str) -> str:
    """Pulls access_token out of a playvalorant.com/opt_in redirect URL."""
    fragment = urlparse(url.strip()).fragment
    params = parse_qs(fragment)
    if "access_token" not in params:
        raise AuthError(
            "Could not find access_token in that URL. Make sure you pasted the full "
            "address bar contents after logging in, including the part after '#'."
        )
    return params["access_token"][0]


def reauth_with_cookies(session: requests.Session) -> str | None:
    """Silently mints a fresh access token from cookies already on the session
    (no username/password/2FA needed). Returns None if the cookies are no
    longer valid and a full interactive login is required.
    """
    resp = session.get(AUTHORIZE_URL, allow_redirects=False, timeout=15)
    location = resp.headers.get("Location", "")
    if "access_token" not in location:
        return None
    return extract_access_token(location)


def checked_json(response: requests.Response, context: str) -> dict:
    """Parses a response as JSON, or raises with a clear diagnostic if it isn't."""
    try:
        return response.json()
    except ValueError:
        raise AuthError(
            f"[{context}] request failed — HTTP {response.status_code}\n"
            f"Response body: {response.text[:500]!r}\n"
            "This usually means the access token is missing/expired, the region "
            "is wrong, or Riot changed the endpoint."
        )


def get_client_version() -> str:
    try:
        return requests.get(VERSION_URL, timeout=10).json()["data"]["riotClientVersion"]
    except Exception:
        return "release-08.05-shipping-9-1234567"  # fallback if valorant-api.com is down


def get_skin_names() -> dict:
    """Maps item (skin level) UUIDs -> display names, best-effort."""
    try:
        data = requests.get(SKINLEVELS_URL, timeout=10).json()["data"]
        return {item["uuid"].lower(): item["displayName"] for item in data}
    except Exception:
        return {}


def game_headers(session: requests.Session, access_token: str) -> tuple[dict, str]:
    """Builds the auth headers for pd.{region} game endpoints. Returns (headers, puuid)."""
    headers = {"Authorization": f"Bearer {access_token}"}
    entitlements_resp = session.post(ENTITLEMENTS_URL, headers=headers, json={})
    entitlements_token = checked_json(entitlements_resp, "entitlements")["entitlements_token"]

    userinfo_resp = session.post(USERINFO_URL, headers=headers, json={})
    puuid = checked_json(userinfo_resp, "userinfo")["sub"]

    headers["X-Riot-Entitlements-JWT"] = entitlements_token
    headers["X-Riot-ClientVersion"] = get_client_version()
    headers["X-Riot-ClientPlatform"] = CLIENT_PLATFORM
    return headers, puuid


def get_tier_names() -> dict:
    """Maps competitive tier number -> readable name, e.g. 21 -> 'Immortal 1'."""
    try:
        episodes = requests.get(COMPETITIVE_TIERS_URL, timeout=10).json()["data"]
        # The last episode holds the current tier naming.
        tiers = episodes[-1]["tiers"]
        return {t["tier"]: t["tierName"].title() for t in tiers}
    except Exception:
        return {}


def get_map_names() -> dict:
    """Maps a map's internal path (mapUrl) -> display name, e.g. Ascent."""
    try:
        data = requests.get(MAPS_URL, timeout=10).json()["data"]
        return {m["mapUrl"]: m["displayName"] for m in data if m.get("mapUrl")}
    except Exception:
        return {}


def fetch_store(session: requests.Session, access_token: str, region: str) -> dict:
    """Given a valid access token, fetches entitlements + puuid + the store."""
    headers, puuid = game_headers(session, access_token)
    # v2 (GET) was deprecated by Riot in favor of v3 (POST).
    store_url = f"https://pd.{region}.a.pvp.net/store/v3/storefront/{puuid}"
    store_resp = session.post(store_url, headers=headers, json={})
    return checked_json(store_resp, "store")


def fetch_competitive(
    session: requests.Session, access_token: str, region: str, count: int = 5
) -> dict:
    """Fetches the player's recent competitive updates (rank + RR per match)."""
    headers, puuid = game_headers(session, access_token)
    url = (
        f"https://pd.{region}.a.pvp.net/mmr/v1/players/{puuid}/competitiveupdates"
        f"?startIndex=0&endIndex={count}&queue=competitive"
    )
    return checked_json(session.get(url, headers=headers), "competitive updates")


def format_store_lines(store: dict) -> list[str]:
    """Human-readable lines describing the store: daily offers + featured bundle."""
    if "SkinsPanelLayout" not in store:
        return [f"Unexpected store response: {store}"]

    names = get_skin_names()
    lines = []

    panel = store["SkinsPanelLayout"]
    offers = panel.get("SingleItemOffers", [])
    seconds_left = panel.get("SingleItemOffersRemainingDurationInSeconds", 0)
    h, r = divmod(seconds_left, 3600)
    m = r // 60
    lines.append(f"**Daily store** (refreshes in {h}h {m}m):")
    for offer_id in offers:
        lines.append(f"- {names.get(offer_id.lower(), offer_id)}")

    featured = store.get("FeaturedBundle") or {}
    # v3 returns a "Bundles" list; older v2-style responses had a single "Bundle".
    bundles = featured.get("Bundles") or ([featured["Bundle"]] if "Bundle" in featured else [])
    for bundle in bundles:
        remaining = bundle.get(
            "DurationRemainingInSeconds", featured.get("BundleRemainingDurationInSeconds", 0)
        )
        h, r = divmod(remaining, 3600)
        m = r // 60
        lines.append(f"\n**Featured bundle** (expires in {h}h {m}m):")
        for entry in bundle.get("Items", []):
            item_id = entry["Item"]["ItemID"]
            lines.append(f"- {names.get(item_id.lower(), item_id)} (base price: {entry['BasePrice']})")

    return lines


def format_rank_lines(comp: dict, count: int = 5) -> list[str]:
    """Human-readable current rank + RR result of the last few competitive matches."""
    matches = comp.get("Matches") or []
    if not matches:
        return ["**Competitive**: no ranked matches found (unranked or no recent comp games)."]

    tier_names = get_tier_names()
    map_names = get_map_names()

    latest = matches[0]
    tier = latest.get("TierAfterUpdate", 0)
    rr = latest.get("RankedRatingAfterUpdate", 0)
    tier_name = tier_names.get(tier, f"Tier {tier}")
    lines = [f"**Current rank**: {tier_name} — {rr} RR"]

    shown = matches[:count]
    lines.append(f"\n**Last {len(shown)} competitive matches**:")
    for m in shown:
        earned = m.get("RankedRatingEarned", 0)
        sign = "+" if earned >= 0 else ""
        result = "won" if earned > 0 else ("lost" if earned < 0 else "draw")
        map_name = map_names.get(m.get("MapID", ""), m.get("MapID", "Unknown map"))
        lines.append(f"- {map_name}: {sign}{earned} RR ({result})")
    return lines


def cookies_to_dict(session: requests.Session) -> dict:
    """Serializes the auth.riotgames.com cookies needed for reauth_with_cookies."""
    return {
        c.name: c.value
        for c in session.cookies
        if c.domain.endswith("riotgames.com")
    }


def cookies_from_dict(session: requests.Session, cookies: dict) -> None:
    for name, value in cookies.items():
        session.cookies.set(name, value, domain="auth.riotgames.com")
