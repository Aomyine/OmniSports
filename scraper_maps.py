import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime, timedelta
import time
import os

RESULTS_URL = "https://www.vlr.gg/matches/results"
OUTPUT      = "vlr_matches_maps.csv"
BASE        = "https://www.vlr.gg"
LIMIT       = 500

SKIP_URL_TERMS = [
    "vct-2026-cn",
    "vct-2025-cn",
    "-cn-",
]

headers = {
    "User-Agent": "Mozilla/5.0"
}

def clean(text):
    return (text or "").strip()

def should_skip(url):
    url_lower = url.lower()
    return any(term in url_lower for term in SKIP_URL_TERMS)

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
    except:
        return ""

# =========================
# LINKS
# =========================
def get_match_links_with_date(limit=500):
    matches_data = []
    seen         = set()
    page         = 1

    while len(matches_data) < limit:
        url = RESULTS_URL if page == 1 else f"{RESULTS_URL}/?page={page}"
        print(f"Pagina {page}: {url}")

        r = requests.get(url, headers=headers, timeout=30)
        soup = BeautifulSoup(r.text, "lxml")

        current_date = None
        elements     = soup.select(".wf-label.mod-large, a.wf-module-item")

        for el in elements:
            if len(matches_data) >= limit:
                break

            if el.name == "div":
                current_date = convert_date(el.get_text(" ", strip=True))

            elif el.name == "a":
                href = el.get("href")
                if href and href.startswith("/"):
                    full_url = BASE + href
                    if full_url not in seen:
                        seen.add(full_url)
                        matches_data.append({
                            "url":  full_url,
                            "date": current_date,
                        })

        page += 1
        time.sleep(0.3)

    return matches_data

# =========================
# MAPAS
# =========================
def get_maps_info(match_url):
    r = requests.get(match_url, headers=headers, timeout=30)
    soup = BeautifulSoup(r.text, "lxml")

    maps = []
    nav_items = soup.select(".vm-stats-gamesnav-item.js-map-switch")

    for item in nav_items:
        game_id = item.get("data-game-id", "")
        href    = item.get("data-href", "")

        if game_id == "all":
            continue
        if item.get("data-disabled", "0") == "1":
            continue

        map_div  = item.select_one("div")
        map_name = ""
        if map_div:
            texts = [t.strip() for t in map_div.stripped_strings]
            map_name = texts[-1] if texts else ""

        map_num   = href.split("?map=")[-1] if "?map=" in href else ""
        full_href = BASE + href if href.startswith("/") else href

        maps.append({
            "game_id":  game_id,
            "map_num":  map_num,
            "map_name": map_name,
            "map_href": full_href,
        })

    return maps

# =========================
# PARSE STAT
# =========================
def parse_stat(td):
    if td is None:
        return ""

    # tenta mod-side mod-both primeiro (padrão da maioria das colunas)
    el = td.select_one("span.mod-side.mod-both")
    if el:
        return clean(el.get_text())

    # fallback para mod-both sem mod-side (caso de Deaths, K/D Diff, FK/FD Diff)
    el = td.select_one("span.mod-both")
    if el:
        return clean(el.get_text())

    return clean(td.get_text())

# =========================
# VALIDACAO
# =========================
def row_has_stats(row):
    return any([
        row.get("ACS"),
        row.get("Kills"),
        row.get("rating"),
    ])

# =========================
# TABELA
# =========================
def scrape_table(table, match_id, match_url, match_date,
                 game_id, map_num, map_name,
                 score_team1, score_team2):
    rows = []

    for tr in table.select("tbody tr"):
        player_el = tr.select_one(".text-of")
        team_el   = tr.select_one(".ge-text-light")

        if not player_el:
            continue

        agent_imgs = tr.select(".mod-agents img")
        agent      = ", ".join(img.get("title", "") for img in agent_imgs)

        all_mod_stat = tr.select("td.mod-stat")

        def ms(i):
            return all_mod_stat[i] if i < len(all_mod_stat) else None

        row = {
            "match_id": match_id,
            "match_url": match_url,
            "match_date": match_date,
            "game_id": game_id,
            "map_num": map_num,
            "map_name": map_name,
            "score_team1": score_team1,
            "score_team2": score_team2,
            "player": clean(player_el.get_text()),
            "team": clean(team_el.get_text()) if team_el else "",
            "agent": agent,
            "rating": parse_stat(ms(0)),
            "ACS": parse_stat(ms(1)),
            "Kills": parse_stat(tr.select_one("td.mod-vlr-kills")),
            "Deaths": parse_stat(tr.select_one("td.mod-vlr-deaths")),
            "Assists": parse_stat(tr.select_one("td.mod-vlr-assists")),
            "K/D Diff": parse_stat(tr.select_one("td.mod-kd-diff")),
            "KAST": parse_stat(ms(6)),
            "ADR": parse_stat(ms(7)),
            "HS%": parse_stat(ms(8)),
            "First Kills": parse_stat(tr.select_one("td.mod-fb")),
            "First Deaths": parse_stat(tr.select_one("td.mod-fd")),
            "First Kill/Death Diff": parse_stat(tr.select_one("td.mod-fk-diff")),
        }

        if row_has_stats(row):
            rows.append(row)

    return rows

# =========================
# MAPA
# =========================
def scrape_map(map_info, match_id, match_date):
    url      = map_info["map_href"]
    game_id  = map_info["game_id"]
    map_num  = map_info["map_num"]
    map_name = map_info["map_name"]

    r = requests.get(url, headers=headers, timeout=30)
    soup = BeautifulSoup(r.text, "lxml")

    block = soup.select_one(f'.vm-stats-game[data-game-id="{game_id}"]')

    if not block:
        return []

    score_team1, score_team2 = "", ""
    scores = block.select(".score")
    if len(scores) >= 2:
        score_team1 = clean(scores[0].get_text())
        score_team2 = clean(scores[1].get_text())

    rows = []
    for table in block.select("table.wf-table-inset.mod-overview"):
        rows.extend(
            scrape_table(
                table, match_id, url, match_date,
                game_id, map_num, map_name,
                score_team1, score_team2
            )
        )

    return rows

# =========================
# MATCH
# =========================
def scrape_match_by_maps(match_url, match_date):
    match_id = match_url.rstrip("/").split("/")[3]
    maps     = get_maps_info(match_url)

    all_rows = []
    for m in maps:
        rows = scrape_map(m, match_id, match_date)
        all_rows.extend(rows)
        time.sleep(0.3)

    return all_rows

# =========================
# MAIN
# =========================
def main():

    # carregar CSV existente
    if os.path.exists(OUTPUT):
        old_df = pd.read_csv(OUTPUT, dtype={"match_id": str})
        existing_keys = set(
            old_df["match_id"].astype(str) + "_" +
            old_df["game_id"].astype(str) + "_" +
            old_df["player"]
        )
        print("CSV existente:", len(old_df))
    else:
        old_df = pd.DataFrame()
        existing_keys = set()
        print("Criando novo CSV")

    matches = get_match_links_with_date(limit=LIMIT)

    new_rows = []

    for i, match in enumerate(matches, start=1):

        url  = match["url"]
        date = match["date"]

        if should_skip(url):
            continue

        print(f"[{i}] {url}")

        try:
            rows = scrape_match_by_maps(url, date)

            for r in rows:
                key = f"{r['match_id']}_{r['game_id']}_{r['player']}"
                if key not in existing_keys:
                    existing_keys.add(key)
                    new_rows.append(r)

        except Exception as e:
            print("Erro:", e)

        time.sleep(0.5)

    new_df = pd.DataFrame(new_rows)

    if not old_df.empty and not new_df.empty:
        final_df = pd.concat([old_df, new_df], ignore_index=True)
    elif not old_df.empty:
        final_df = old_df
    else:
        final_df = new_df

    final_df.to_csv(OUTPUT, index=False, encoding="utf-8-sig")

    print("FINAL:", len(final_df))

if __name__ == "__main__":
    main()
