import os
import time
import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime, timedelta

headers = {"User-Agent": "Mozilla/5.0"}
BASE = "https://www.vlr.gg"
CSV_FILE = "vlr_matches_raw.csv"

def clean(text):
    return (text or "").strip()

# =========================
# DATA
# =========================
def convert_date(date_str):
    try:
        text = clean(date_str)

        if "Today" in text:
            return datetime.today().strftime("%Y-%m-%d")

        if "Yesterday" in text:
            return (datetime.today() - timedelta(days=1)).strftime("%Y-%m-%d")

        base_text = text.split("Today")[0].split("Yesterday")[0].strip()
        return datetime.strptime(base_text, "%a, %B %d, %Y").strftime("%Y-%m-%d")

    except Exception as e:
        print(f"Erro ao converter data '{date_str}': {e}")
        return ""

# =========================
# LINKS + DATA (CORRETO)
# =========================
def get_match_links_with_date(pages=5, limit=200):
    matches_data = []
    seen = set()

    for page in range(1, pages + 1):
        url = "https://www.vlr.gg/matches/results" if page == 1 else f"https://www.vlr.gg/matches/results/?page={page}"
        print("Coletando:", url)

        r = requests.get(url, headers=headers, timeout=30)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "lxml")

        current_date = None
        elements = soup.select(".wf-label.mod-large, a.wf-module-item")

        for el in elements:

            # pega data
            if el.name == "div" and "wf-label" in el.get("class", []):
                current_date = convert_date(el.get_text(" ", strip=True))

            # pega link
            elif el.name == "a":
                href = el.get("href")

                if href and href.startswith("/"):
                    full_url = BASE + href

                    if full_url not in seen:
                        seen.add(full_url)
                        matches_data.append({
                            "url": full_url,
                            "date": current_date
                        })

            if len(matches_data) >= limit:
                return matches_data

        time.sleep(0.5)

    return matches_data

# =========================
# SCRAPE MATCH
# =========================
def scrape_match(match_url, match_date):

    r = requests.get(match_url, headers=headers, timeout=30)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "lxml")
    match_id = match_url.split("/")[3]

    rows = []
    tbodys = soup.select("tbody")[:2]

    for tb in tbodys:
        for tr in tb.select("tr"):

            name = tr.select_one(".text-of")
            team = tr.select_one(".ge-text-light")

            if not name:
                continue

            player = clean(name.get_text())
            team = clean(team.get_text()) if team else ""

            raw_stats = [clean(x.get_text()) for x in tr.select(".mod-stat .mod-both")]

            stats = [s for s in raw_stats if s and not s.startswith("+") and not s.startswith("-")]

            if len(stats) < 10:
                continue

            rating, acs, k, d, a, kast, adr, hs, fk, fd = stats[:10]

            # FK/FD DIFF CALCULADO (FIX)
            def to_int(x):
                try:
                    return int(float(str(x)))
                except:
                    return 0

            fk_diff = to_int(fk) - to_int(fd)

            rows.append({
                "match_id": match_id,
                "match_url": match_url,
                "match_date": match_date,
                "player": player,
                "team": team,
                "rating": rating,
                "ACS": acs,
                "Kills": k,
                "Deaths": d,
                "Assists": a,
                "K/D Diff": "",  # opcional manter vazio
                "KAST": kast,
                "ADR": adr,
                "HS%": hs,
                "First Kills": fk,
                "First Deaths": fd,
                "First Kill/Death Diff": fk_diff
            })

    return match_id, rows

# =========================
# MAIN
# =========================
def main():

    if os.path.exists(CSV_FILE):
        old_df = pd.read_csv(CSV_FILE)
        existing_ids = set(old_df["match_id"].astype(str).unique())
        print("CSV carregado:", len(existing_ids))
    else:
        old_df = pd.DataFrame()
        existing_ids = set()
        print("Criando novo CSV")

    matches = get_match_links_with_date(pages=5, limit=200)

    print("Links coletados:", len(matches))

    new_rows = []
    new_matches = 0

    for i, match in enumerate(matches, start=1):

        match_id = match["url"].split("/")[3]

        if match_id in existing_ids:
            continue

        print(f"[{i}/{len(matches)}] {match['url']} | data={match['date']}")

        try:
            mid, rows = scrape_match(match["url"], match["date"])

            if not rows:
                continue

            new_rows.extend(rows)
            existing_ids.add(mid)
            new_matches += 1

        except Exception as e:
            print("Erro:", match["url"], e)

        time.sleep(0.5)

        if new_matches >= 200:
            break

    print("Novas partidas:", new_matches)

    new_df = pd.DataFrame(new_rows)

    if not old_df.empty and not new_df.empty:
        final_df = pd.concat([old_df, new_df], ignore_index=True)
    elif not old_df.empty:
        final_df = old_df
    else:
        final_df = new_df

    if not final_df.empty:
        final_df["match_id"] = final_df["match_id"].astype(str)
        final_df = final_df.drop_duplicates(subset=["match_id", "player"], keep="first")

    final_df.to_csv(CSV_FILE, index=False, encoding="utf-8-sig")

    print("\nFINALIZADO")
    print("Linhas:", len(final_df))

if __name__ == "__main__":
    main()
