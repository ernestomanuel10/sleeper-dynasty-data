#!/usr/bin/env python3
"""Fetch public Sleeper league data for 2025 and 2026."""
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

LEAGUES = {"2025": "1256661729216057344", "2026": "1312063648402776064"}
BASE = "https://api.sleeper.app/v1"
HEADERS = {"User-Agent": "dynasty-league-archive/1.0", "Accept": "application/json"}

def fetch(path):
    url = f"{BASE}/{path}"
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=35) as response:
                return json.load(response)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            if attempt == 3:
                raise
            time.sleep(2 ** attempt)

def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

def main():
    for year, league_id in LEAGUES.items():
        root = Path("data") / year
        print(f"Fetching {year} league {league_id}", flush=True)
        league = fetch(f"league/{league_id}")
        if not isinstance(league, dict) or not league.get("league_id"):
            raise RuntimeError(f"League {league_id} not found")
        save(root / "league.json", league)
        users = fetch(f"league/{league_id}/users")
        rosters = fetch(f"league/{league_id}/rosters")
        save(root / "users.json", users)
        save(root / "rosters.json", rosters)
        save(root / "traded_picks.json", fetch(f"league/{league_id}/traded_picks"))
        save(root / "winners_bracket.json", fetch(f"league/{league_id}/winners_bracket"))
        save(root / "losers_bracket.json", fetch(f"league/{league_id}/losers_bracket"))
        save(root / "drafts.json", fetch(f"league/{league_id}/drafts"))
        settings = league.get("settings") or {}
        playoff_start = int(settings.get("playoff_week_start") or 15)
        # All weeks through championship; fetch 1..18 to avoid missing custom formats.
        all_matchups = []
        all_transactions = []
        for week in range(1, 19):
            matchups = fetch(f"league/{league_id}/matchups/{week}")
            transactions = fetch(f"league/{league_id}/transactions/{week}")
            save(root / "matchups" / f"week_{week:02d}.json", matchups)
            save(root / "transactions" / f"week_{week:02d}.json", transactions)
            for m in matchups or []:
                all_matchups.append({"week": week, **m})
            for t in transactions or []:
                all_transactions.append({"week": week, **t})
        save(root / "matchups.json", all_matchups)
        save(root / "transactions.json", all_transactions)
        roster_to_user = {r["roster_id"]: r.get("owner_id") for r in rosters}
        users_by_id = {u["user_id"]: u for u in users}
        standings = []
        for r in rosters:
            s = r.get("settings") or {}
            owner = users_by_id.get(roster_to_user.get(r["roster_id"]), {})
            standings.append({
                "roster_id": r["roster_id"],
                "owner_id": r.get("owner_id"),
                "display_name": owner.get("display_name"),
                "wins": s.get("wins", 0), "losses": s.get("losses", 0),
                "ties": s.get("ties", 0),
                "points_for": float(s.get("fpts", 0)) + float(s.get("fpts_decimal", 0)) / 100,
                "points_against": float(s.get("fpts_against", 0)) + float(s.get("fpts_against_decimal", 0)) / 100,
            })
        standings.sort(key=lambda x: (x["wins"], -x["losses"], x["points_for"]), reverse=True)
        save(root / "standings.json", standings)
        print(f"{year}: {len(rosters)} rosters, {len(all_matchups)} matchup roster entries, {len(all_transactions)} transactions", flush=True)

if __name__ == "__main__":
    main()
