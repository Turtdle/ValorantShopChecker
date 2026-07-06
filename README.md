# Valorant Shop Checker

Check your Valorant store from the command line, or have a scheduled GitHub
Action post your daily shop to Discord automatically.

## Local use

```bash
pip install -r requirements.txt
python scripts/check_store.py
```

You'll be prompted to either paste a login redirect URL from your browser, or
log in with your Riot username/password (with a 2FA prompt if enabled). Your
credentials only ever go to Riot's own auth servers.

Pass a different region if you're not on NA:

```bash
python scripts/check_store.py --region eu   # na, eu, ap, kr
```

## Automated Discord notifier (GitHub Action)

The included workflow (`.github/workflows/valorant-store.yml`) runs daily and
posts your shop to a Discord webhook. Because the Action runs unattended, it
can't answer a 2FA prompt — instead it reuses a saved Riot session.

### One-time setup

1. **Seed a reusable session** (run locally):

   ```bash
   python scripts/bootstrap_cookies.py
   ```

   Log in once; it prints a JSON blob of session cookies.

2. **Add three repo secrets** (Settings → Secrets and variables → Actions):

   | Secret | Value |
   | --- | --- |
   | `RIOT_COOKIES` | the JSON printed by `bootstrap_cookies.py` |
   | `DISCORD_WEBHOOK_URL` | a Discord channel webhook URL |
   | `GH_PAT` | a classic PAT with `repo` scope (lets the workflow refresh `RIOT_COOKIES` when Riot rotates the cookie) |

3. **Test it** — Actions tab → *Valorant Store Check* → *Run workflow*.

The schedule is `0 1 * * *` (01:00 UTC ≈ 5pm PST). Adjust the `cron` in the
workflow if your store resets at a different time. Note cron doesn't follow
DST, so it shifts by an hour between PST/PDT.

If Riot's session eventually expires, the Action posts a warning to Discord —
just rerun `bootstrap_cookies.py` and update the `RIOT_COOKIES` secret.

## Credits

Auth flow and store endpoint based on the community
[ValorantClientAPI](https://github.com/HeyM1ke/ValorantClientAPI) docs.
