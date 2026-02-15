import json
import re
from datetime import datetime, timezone, date

import requests
from bs4 import BeautifulSoup

URL = "https://www.skysports.com/watch/football-on-sky"
HEADERS = {
    "User-Agent": "PubFixturesBot/1.0 (+https://stokeanddagger.github.io/pub-fixtures/)"
}

# Matches "Sat 14th February" etc
DATE_RE = re.compile(
    r"^(Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+(\d{1,2})(st|nd|rd|th)\s+([A-Za-z]+)$"
)
TIME_RE = re.compile(r"^\d{1,2}:\d{2}$")
SKY_RE = re.compile(r"\bSky Sports\b", re.I)

MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12
}

IGNORE_LINES = {
    "Match Preview",
    "Remote record",
    "Load More",
    "Full Football Fixtures List",
    "Full Fixtures & Results",
}


def clean(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())


def strip_times_in_parens(s: str) -> str:
    # "Sky Sports Main Event (11:00)" -> "Sky Sports Main Event"
    return re.sub(r"\s*\([^)]*\)\s*", "", s).strip()


def parse_date_label(label: str, year: int) -> tuple[str | None, int | None]:
    """
    Returns (iso_date, month_number) or (None, None)
    """
    m = DATE_RE.match(label)
    if not m:
        return None, None
    day = int(m.group(2))
    month_name = m.group(4).lower()
    month = MONTHS.get(month_name)
    if not month:
        return None, None
    return date(year, month, day).isoformat(), month


def scrape() -> dict:
    resp = requests.get(URL, headers=HEADERS, timeout=25)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")

    raw_lines = soup.get_text("\n", strip=True).split("\n")
    lines = [clean(l) for l in raw_lines if clean(l)]
    lines = [l for l in lines if l not in IGNORE_LINES]

    fixtures = []
    current_label = None
    current_iso = None

    now_utc = datetime.now(timezone.utc)
    year = now_utc.year
    last_month = None

    i = 0
    while i < len(lines):
        line = lines[i]

        # Date heading on Sky is usually "Sat 14th February" (no ###),
        # but we strip it anyway in case some renderers add it.
        candidate = line.replace("### ", "").strip()

        iso, month = parse_date_label(candidate, year)
        if iso and month:
            current_label = candidate

            # Year rollover safety (Dec -> Jan)
            if last_month is not None and month < last_month:
                year += 1
                iso, month = parse_date_label(current_label, year)

            last_month = month
            current_iso = iso
            i += 1
            continue

        # Look for match triplet: team, time, team
        if current_iso and i + 2 < len(lines):
            home = line
            kickoff = lines[i + 1]
            away = lines[i + 2]

            if TIME_RE.match(kickoff):
                # Find the meta line within the next few lines that contains "..., Sky Sports..."
                meta = None
                j = i + 3
                while j < min(i + 12, len(lines)):
                    if SKY_RE.search(lines[j]):
                        meta = lines[j]
                        break
                    j += 1

                if meta:
                    # Often: "Bundesliga, Sky Sports Football (17:20)"
                    parts = [p.strip() for p in meta.split(",")]
                    competition = parts[0]

                    # Everything after the first comma is channels (sometimes multiple)
                    channel_parts = parts[1:] if len(parts) > 1 else []

                    tv_channels = []
                    for cp in channel_parts:
                        name = strip_times_in_parens(cp)
                        if name:
                            tv_channels.append(name)

                    # If Sky line didn’t have commas, we can’t split out competition/channels cleanly.
                    # In that case, skip rather than adding garbage.
                    if tv_channels:
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

                        i = j + 1
                        continue

        i += 1

    return {
        "source": "skysports-watch-football-on-sky",
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
