# Notes: sources, what we tried, results

In September 2026 Estonia's Ministry of the Interior published every death in
the population register since 1926 as open data. This repo is an attempt to do
something more useful with it than list it: find each person's grave. It holds
the scripts, the burial data collected so far, and an account of what worked
and what didn't.

**Where it stands (8 October 2026):** 48,955 people in the death register are
matched to a grave in Tartu with a plot code and coordinates. A proof-of-concept
scrape of the national cemetery portal matched 77% of what it fetched and was
blocked after about 450 requests.

## What's in the repo

| Path | Contents |
|---|---|
| `data/tartu/rows.jsonl` | All 84,193 burials from Tartu's public cemetery layer, with coordinates |
| `data/tartu/matches.csv` | The 49,001 Tartu burials matched to a death record |
| `data/saaremaa/rows.jsonl`, `matches.csv` | All 50,044 Saaremaa burials, and the 27,727 matched to a death record |
| `data/haudi/rows.jsonl` | 1,548 burials from kalmistud.ee (nine surnames, 119 cemeteries) |
| `data/haudi/matches.csv` | The 946 of those matched to a death record |
| `data/haudi/terms.txt` | The 37,134 search terms a full kalmistud.ee listing would need |
| `data/haudi/poc_terms.txt`, `done.jsonl` | The surname sample used for the proof of concept, and which ones finished |
| `scripts/` | Everything that produced the above |

Paths in this file are relative to the repo root.

The death records themselves (97 MB) are not committed. `scripts/fetch_register.py`
downloads them into `data/raw/`.

`matches.csv` columns: `first_name, surname, born, died` come from the death
register; `buried, cemetery, plot, lat, lon` from the cemetery; `match` says
which rule paired them (see [Matching](#matching)). Personal ID codes are in
the ministry's file but are not copied into anything here.

## The sources

### Death records

[Surmaandmed](https://andmed.eesti.ee/datasets/surmaandmed), Ministry of the
Interior, CC BY 4.0. Five columns: first name, surname, personal ID code, birth
date, death date. Refreshed daily with a seven-day delay; the ministry notes
that corrections do not reach copies downloaded earlier.

| | |
|---|---|
| Records (8 Oct 2026) | 1,732,767 |
| Earliest death | 1 July 1926 |
| Distinct surnames | 159,901 |
| No ID code | 190,091 |
| No birth date | 188,668 |
| No first name | 10,374 |

### Burials

Estonia has three separate cemetery systems.

| System | Covers | Access |
|---|---|---|
| Tartu City Government, [gis.tartulv.ee/kalmistud](https://gis.tartulv.ee/kalmistud/) | Tartu's 15 cemeteries | A public ArcGIS feature service, [`Kalmistu/KA_avalik_maetu`](https://gis.tartulv.ee/arcgis/rest/services/Kalmistu/KA_avalik_maetu/FeatureServer/0). 10,000 records a request |
| Haudi, [kalmistud.ee](https://www.kalmistud.ee) | About 234 cemeteries across the country | Name search only. No bulk download or API |
| Saaremaa municipality, [gis.saaremaavald.ee/kalmistud](https://gis.saaremaavald.ee/kalmistud/) | Saaremaa's 33 cemeteries | The same public ArcGIS layer as Tartu, [`Kalmistud/KA_avalik_maetu`](https://gis.saaremaavald.ee/arcgis/rest/services/Kalmistud/KA_avalik_maetu/FeatureServer/0). 1,000 records a request. No licence stated |

Haudi is software built and run by AS Spin TEK. Each municipality that joined
typed in its own cemetery books and headstone inventories, and stays the owner
of that data; the portal says outright that the records are incomplete and
that not every municipality signed up.

## What we tried

### 1. Looked at the existing site

[surmaregister.ee](https://surmaregister.ee/en) went live on 30 September 2026
on the same death records. It has year, month and person pages and a search.
Its person pages show the five source fields including the full ID code, some
arithmetic on the dates, and a link to the kalmistud.ee search form. Since
3 October every page with a person on it is `noindex`; the sitemap lists 208
pages. It has no burial data.

### 2. Tried to list kalmistud.ee

The portal's search needs a surname: exact, or three or more letters matched
anywhere in it. It returns 20 rows a page: name, birth, death and burial dates,
plot address, cemetery. Searching by cemetery or date alone returns nothing.

`scripts/haudi_cover.py` works out the cheapest set of search terms that
reaches every surname in the death register. The answer is 37,134 terms and
about 335,000 requests, which is five days at one request every 1.3 seconds.

`scripts/scrape_haudi.py` ran as a ten-minute proof of concept on a random
sample of surnames. **About six minutes and 450 requests in, the portal
started refusing connections from our address** on ports 80 and 443 while
staying up for everyone else. We stopped there and did not try another address.

### 3. Found Tartu's open layer

Tartu publishes its cemeteries on the national open data portal
([Tartu kalmistute kaardirakendus](https://andmed.eesti.ee/datasets/tartu-kalmistute-kaardirakendus),
CC BY-SA 3.0). The portal entry points at a service that needs a login
(`KA_koond`), but the same server has a public layer, `KA_avalik_maetu`, that
answers queries without one. `scripts/fetch_tartu.py` downloaded all of it in
nine requests.

Every row has a name, a plot code, a cemetery and the plot's position. Dates
are thinner: 78,304 rows have a burial date, 14,054 a death date and 13,773 a
birth date.

### 4. Found Saaremaa's too

Saaremaa runs the same cemetery software as Tartu and exposes the same public
layer. `scripts/fetch_saaremaa.py` downloaded 50,044 burials in 51 requests.
Its dates are fuller than Tartu's (40,916 rows have a death date) and 48,493
rows link a headstone photo.

A search of the national open data portal for every cemetery and burial term
found no other municipality. It did find four listings by Spin TEK pointing at
kalmistud.ee, one of them "Eestis maetute register", marked public and
unrestricted, with a link to the website and no file or API.

## Results

| Source | Burials from July 1926 on | Matched to a death record |
|---|---|---|
| Tartu (complete) | 76,185 | 49,001 (64%), all with coordinates |
| Saaremaa (complete) | 35,715 | 27,727 (78%), 27,410 with coordinates |
| kalmistud.ee (nine surnames) | 1,234 | 946 (77%) |

For the seven kalmistud.ee surnames fetched in full, 240 of the register's 632
people (38%) had a grave on the portal.

### Matching

`scripts/join_burials.py` pairs a burial with a register record of the same
surname by the strictest rule that fits:

| Rule | Requires | Tartu | Saaremaa | kalmistud.ee |
|---|---|---|---|---|
| `exact` | first name, birth date and death date equal | 12,275 | 18,903 | 468 |
| `dates` | birth and death dates equal, first name spelled differently | 76 | 1,009 | 92 |
| `name+death` | first name and death date equal, birth date missing on one side | 271 | 1,757 | 173 |
| `name+birth` | first name and birth date equal, same death year | 182 | 732 | 21 |
| `name+burial` | first name equal, buried 0 to 45 days after the registered death | 36,140 | 133 | 64 |
| `name+years` | first name equal, same birth and death year | 57 | 5,193 | 128 |

Three quarters of the Tartu matches are `name+burial`, because most Tartu rows
have no death date. For common names that rule will pair some burials with the
wrong person of the same name. The error rate has not been measured; filter on
`match` if you need only the certain ones.

## Running it

Standard-library Python 3.9+, no dependencies. Run the scripts with `python3 -I`.

```sh
python3 -I scripts/fetch_register.py                  # death records -> data/raw/
python3 -I scripts/fetch_tartu.py                     # Tartu burials -> data/tartu/rows.jsonl
python3 -I scripts/join_burials.py data/tartu/rows.jsonl
python3 -I scripts/join_burials.py data/haudi/rows.jsonl
```

| Script | What it does |
|---|---|
| `fetch_register.py` | Downloads the ministry's two death-record files. |
| `fetch_tartu.py` | Downloads Tartu's public burial layer with each plot's coordinates. |
| `join_burials.py` | Matches burial rows from either source to death records and prints the rates. Writes `matches.csv` and `joined.jsonl` beside the input. |
| `fetch_saaremaa.py` | Downloads Saaremaa's public burial layer with plot coordinates and headstone photo links. |
| `scrape_surmaregister.py` | Scrapes surmaregister.ee's month pages for its full index of people. |
| `show_matches.py` | Prints a sample of matched people and their graves from a `matches.csv`. |
| `make_showcase.py` | Renders `docs/showcase.mp4`. Needs numpy, Pillow and ffmpeg: `uv run --python 3.12 --with numpy --with pillow scripts/make_showcase.py`. |
| `haudi_cover.py` | Picks the search terms that reach every register surname on kalmistud.ee in the fewest pages. |
| `scrape_haudi.py` | Scrapes kalmistud.ee by running a term list through its name search, one request at a time. Resumable; stops on a block or captcha. |
