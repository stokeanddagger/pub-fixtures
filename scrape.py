import json
import re
from datetime import datetime, timezone, date

import requests
from bs4 import BeautifulSoup

# Live Football On TV - Premier League listings
URL = "https://www.live-footballontv.com/live-premier-league-football-on-tv.html"
HEADERS = {
    "User-Agent": "PubFixturesBot/1.0 (+https://stokeanddagger.github.io/pub-fixtures/)"
}

# Example on page: "Wednesday 18th February 2026"
FULL_DATE_RE = re.compile(
    r"^(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\s+(\d{1,2})(st|nd|rd|th)\s+([A-Za-z]+)\s+(\d{4})$"
)
TIME_RE = re.compile(r"^\d{1,2}:\d{2}$")

MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12
}

def clean(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())

def parse_full_date(label: str) -> str | None:
    m = FULL_DATE_RE.match(label)
    if not m:
        return None
    day = int(m.group(2))
    month_name = m.group(4).lower()
    year = int(m.group(5))
    month = MONTHS.get(month_name)
    if not month:
        return None
    return date(year, month, day).isoformat()

def extract_channels(ch_line: str) -> list[str]:
    """
    Example line:
      "Sky Sports Main Event Sky Sports Premier League Sky Sports Ultra HDR"
      "TNT Sports 1 TNT Sports Ultimate"
      "Sky Sports+"
      "Sky Sports TBC"
    We split into channels whenever we see "Sky Sports*" or "TNT Sports*".
    """
    tokens = ch_line.split()
    channels: list[str] = []

    def is_prefix(i: int) -> bool:
        if i + 1 >= len(tokens):
            return False
        # Sky Sports / Sky Sports+ / Sky SportsHD etc
        if tokens[i] == "Sky" and tokens[i + 1].startswith("Sports"):
            return True
        if tokens[i] == "TNT" and tokens[i + 1].startswith("Sports"):
            return True
        return False

    i = 0
    while i < len(tokens):
        if not is_prefix(i):
            i += 1
            continue

        start = i
        i += 2
        while i < len(tokens) and not is_prefix(i):
            i += 1
        channels.append(" ".join(tokens[start:i]).strip())

    # De-dupe while preserving order
    seen = set()
    out = []
    for c in channels:
        if c and c not in seen:
            seen.add(c)
            out.append(c)
    return out

def scrape() -> dict:
    resp = requests.get(URL, headers=HEADERS, timeout=25)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    raw_lines = soup.get_text("\n", strip=True).split("\n")
    lines = [clean(l) for l in raw_lines if clean(l)]

    fixtures = []
    current_label = None
    current_iso = None

    i = 0
    while i < len(lines):
        line = lines[i]

        # Date heading, e.g. "Saturday 21st February 2026"
        iso = parse_full_date(line)
        if iso:
            current_label = line
            current_iso = iso
            i += 1
            continue

        # Expect: time -> "Home v Away" -> "Premier League" -> channels line
        if current_iso and TIME_RE.match(line) and i + 3 < len(lines):
            kickoff = line
            match_line = lines[i + 1]
            competition = lines[i + 2]
            channels_line = lines[i + 3]

            if " v " in match_line:
                home, away = [clean(x) for x in match_line.split(" v ", 1)]
                tv_channels = extract_channels(channels_line)

                # Keep only Sky/TNT matches
                if tv_channels and any(c.startswith(("Sky Sports", "TNT Sports")) for c in tv_channels):
                    match_id = f"{current_iso}-{kickoff}-{home}-{away}".lower()
                    match_id = re.sub(r"[^a-z0-9]+", "-", match_id).strip("-")

                    fixtures.append({
                        "id": match_id,
                        "date_label": current_label,
                        "date": current_iso,
                        "kickoff_time": kickoff,
                        "home": home,
                        "away": away,
                        "competition": competition,
                        "tv_channels": tv_channels
                    })

                    i += 4
                    continue

        i += 1

    return {
        "source": "live-footballontv-premier-league",
        "source_url": URL,
        "generated_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "timezone": "Europe/London",
        "fixtures": fixtures
    }

if __name__ == "__main__":
    data = scrape()
    with open("fixtures.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Wrote {len(data['fixtures'])} fixtures")
