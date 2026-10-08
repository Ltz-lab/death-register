# death-register

Estonia's open death records, joined to where people are buried.

## Data

**Death records.** The Ministry of the Interior publishes every death entered in
the population register since 1 July 1926 as open data
([Surmaandmed](https://andmed.eesti.ee/datasets/surmaandmed), CC BY 4.0):
first name, surname, personal ID code, birth date and death date. About 1.73
million rows, refreshed daily with a seven-day delay. The files live at
`https://opendata.smit.ee/etl/rahvastik/`:

| File | Covers |
|---|---|
| `surmaandmed_1926_kuni_eelmise_aasta_lopuni.csv` | 1926 to the end of last year |
| `surmaandmed_jooksev_aasta.csv` | the current year |

Download both into `data/raw/`. `data/` is not committed.

**Burials.** Estonia has three separate cemetery systems:

| System | Covers | Access |
|---|---|---|
| Tartu City Government, [gis.tartulv.ee/kalmistud](https://gis.tartulv.ee/kalmistud/) | Tartu's 15 cemeteries, 84,193 burials with plot polygons | Open data (CC BY-SA 3.0): a public ArcGIS feature service, `Kalmistu/KA_avalik_maetu` |
| Haudi, [kalmistud.ee](https://www.kalmistud.ee) | About 234 cemeteries whose municipalities entered their cemetery books and headstone inventories | Name search only, no bulk download. Its terms of service forbid automated collection, and it blocks addresses that try |
| Saaremaa municipality, [saaremaavald.ee/kalmistud](https://www.saaremaavald.ee/kalmistud/) | Saaremaa's cemeteries | Not looked at yet |

## Scripts

Standard-library Python 3.9+, no dependencies. Run them with `python3 -I`.

| Script | What it does |
|---|---|
| `scripts/haudi_cover.py` | Picks the surname search terms that reach every surname in the death register in the fewest result pages. Writes `data/haudi/terms.txt`. |
| `scripts/scrape_haudi.py` | Walks a list of terms through the portal's name search, one request at a time, and appends rows to `data/haudi/rows.jsonl`. Resumable; stops on a block or captcha. |
| `scripts/fetch_tartu.py` | Downloads Tartu's public burial layer into `data/tartu/rows.jsonl`, with each plot's coordinates. |
| `scripts/join_burials.py` | Matches burial rows from either source to death records by surname, first name and dates, and prints the match rates. Writes `joined.jsonl` beside the input. |

```sh
python3 -I scripts/fetch_tartu.py
python3 -I scripts/join_burials.py data/tartu/rows.jsonl
```

## Results so far

| Source | Burials from July 1926 on | Matched to a death record |
|---|---|---|
| Tartu (complete) | 76,185 | 49,001 (64%), all with coordinates |
| kalmistud.ee (nine surnames, before the block) | 1,234 | 946 (77%) |

Most Tartu rows carry only a burial date, so 36,140 of its matches rest on
first name, surname and a burial 0 to 45 days after the registered death.
