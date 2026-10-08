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
| Saaremaa municipality, [saaremaavald.ee/kalmistud](https://www.saaremaavald.ee/kalmistud/) | Saaremaa's cemeteries | Not looked at yet |

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

The portal's [terms of service](https://www.kalmistud.ee/info/terms-of-service)
(updated 27 February 2025) forbid this. Section 5 bans "mass downloading
(scraping), copying or aggregating by any method", automated queries, and
collecting the data to build a database; section 6 lets the operator block
access, claim damages and demand the collected data be destroyed. The 1,548
rows in `data/haudi/` were collected against those terms.

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

## Results

| Source | Burials from July 1926 on | Matched to a death record |
|---|---|---|
| Tartu (complete) | 76,185 | 49,001 (64%), all with coordinates |
| kalmistud.ee (nine surnames) | 1,234 | 946 (77%) |

For the seven kalmistud.ee surnames fetched in full, 240 of the register's 632
people (38%) had a grave on the portal.

### Matching

`scripts/join_burials.py` pairs a burial with a register record of the same
surname by the strictest rule that fits:

| Rule | Requires | Tartu | kalmistud.ee |
|---|---|---|---|
| `exact` | first name, birth date and death date equal | 12,275 | 468 |
| `dates` | birth and death dates equal, first name spelled differently | 76 | 92 |
| `name+death` | first name and death date equal, birth date missing on one side | 271 | 173 |
| `name+birth` | first name and birth date equal, same death year | 182 | 21 |
| `name+burial` | first name equal, buried 0 to 45 days after the registered death | 36,140 | 64 |
| `name+years` | first name equal, same birth and death year | 57 | 128 |

Three quarters of the Tartu matches are `name+burial`, because most Tartu rows
have no death date. For common names that rule will pair some burials with the
wrong person of the same name. The error rate has not been measured; filter on
`match` if you need only the certain ones.

## Open questions

- **Tartu's licence.** The open data listing names `KA_koond`, not the public
  layer used here. Whether CC BY-SA 3.0 covers `KA_avalik_maetu` should be
  confirmed with Tartu before anything built on it is published. If it does,
  share-alike applies to what's derived from it.
- **The rest of the country.** kalmistud.ee cannot be listed at a pace it
  tolerates. The municipalities own those records and could be asked for them
  directly; Spin TEK could be asked for an export.
- **Saaremaa** has its own system that nobody has looked at.
- **Showing people's pages.** Estonia's Personal Data Protection Act §9(4)
  says no heir's consent is needed to process a dead person's name, sex, birth
  and death dates, the fact of death, and the time and place of burial. The ID
  code is not on that list. This was read from search-result snippets of the
  act, not the full text, and is not legal advice.

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
| `show_matches.py` | Prints a sample of matched people and their graves from a `matches.csv`. |
| `haudi_cover.py` | Picks the search terms that reach every register surname on kalmistud.ee in the fewest pages. |
| `scrape_haudi.py` | Walks a term list through the kalmistud.ee name search, one request at a time. Resumable; stops on a block or captcha. |

## Credits

Death records: Ministry of the Interior of Estonia, "Surmaandmed",
andmed.eesti.ee, CC BY 4.0. Tartu burials: Tartu City Government.
