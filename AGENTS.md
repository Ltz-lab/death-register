# death-register Agent Guide

## Purpose

Join Estonia's open death records to where people are buried, and do it better
than listing the records. `README.md` is the short version; `docs/notes.md` has
the sources, what was tried, the match rules and the open questions. Read
`docs/notes.md` before proposing a new data source: several have already been
tried or ruled out.

## Project map

- `scripts/` - everything that fetches, joins and shows data. Standard-library
  Python 3.9+, no dependencies, no package layout: each script runs on its own.
- `data/raw/` - the ministry's two death-record CSVs. Gitignored (97 MB);
  `scripts/fetch_register.py` downloads them.
- `data/tartu/` - Tartu's public burial layer (`rows.jsonl`, committed) and its
  matches (`matches.csv`, committed).
- `data/haudi/` - the kalmistud.ee proof of concept: the rows fetched before the
  block, the surname sample, the full term list, and their matches. Committed.
- `joined.jsonl` (in either data folder) - every burial row with its match.
  Gitignored; `join_burials.py` rebuilds it.
- `docs/notes.md` - the full account. `docs/records.gif` - the README recording.

| Script | Does |
|---|---|
| `fetch_register.py` | Downloads the death records into `data/raw/`. |
| `fetch_tartu.py` | Downloads Tartu's burial layer with plot coordinates. |
| `join_burials.py` | Matches burial rows to death records; writes `matches.csv` and `joined.jsonl` beside the input. |
| `show_matches.py` | Prints a sample of matched people and graves. |
| `haudi_cover.py` | Picks the kalmistud.ee search terms that reach every register surname. |
| `scrape_haudi.py` | Walks terms through the kalmistud.ee name search. See "Access rules" before running it. |

## Commands

```sh
python3 -I scripts/fetch_register.py
python3 -I scripts/fetch_tartu.py
python3 -I scripts/join_burials.py data/tartu/rows.jsonl
python3 -I scripts/join_burials.py data/haudi/rows.jsonl
python3 -I scripts/show_matches.py data/tartu/matches.csv --match exact
```

Run scripts with `python3 -I`. The data folders hold downloaded and scraped
files, and `-I` keeps Python from importing anything out of the working
directory. There are no tests; the check for a change to the join is to rerun
it on both sources and compare the printed rates with `docs/notes.md`.

## Data rules

- **No personal ID codes in anything written or committed.** The ministry's CSV
  has them (`isikukood`); `join_burials.py` drops the column on load. The
  consent exemption in Estonia's Personal Data Protection Act §9(4) covers a
  dead person's name, sex, birth and death dates, fact of death, and burial
  time and place, and the ID code is not on that list.
- The death records are regenerated daily and the ministry does not push
  corrections to old copies. `fetch_register.py` overwrites; nothing here keeps
  history yet.
- Register names are upper case; burial names are mixed case with spaces
  around hyphens. Compare through `first_name()` in `join_burials.py`.
- Many rows are partial: 188,668 register records have no birth date, and most
  Tartu rows have only a burial date. A missing value is `""` after loading
  (`-` in the ministry's file).
- `matches.csv` takes name and dates from the register and the burial fields
  from the cemetery. The `match` column is the rule that paired them, strictest
  first: `exact`, `dates`, `name+death`, `name+birth`, `name+burial`,
  `name+years`. `name+burial` (buried 0 to 45 days after the registered death)
  is three quarters of the Tartu matches and will mispair some common names;
  its error rate has not been measured. Anything that needs certainty should
  filter on `match`.
- When numbers in `README.md` or `docs/notes.md` change, change both.

## Access rules

- **Death records** (`opendata.smit.ee`) and **Tartu** (`gis.tartulv.ee`,
  layer `Kalmistu/KA_avalik_maetu`) are open data with real download
  endpoints. Fetch them freely. Tartu's licence is CC BY-SA 3.0 as listed for a
  sibling service; whether it covers this layer is unconfirmed.
- **kalmistud.ee is off limits for now.** Its terms forbid automated
  collection, and on 8 October 2026 it blocked this network's address about 450
  requests into a test run. Do not rerun `scrape_haudi.py`, and do not route it
  through a VPN, proxy or another machine: that decision was made explicitly.
  The route for that data is asking the municipalities or AS Spin TEK.
- **Saaremaa** (`saaremaavald.ee/kalmistud`) has not been looked at. Read its
  terms and look for an open endpoint before fetching anything in bulk.
- Any new source: check for an open-data listing on `andmed.eesti.ee` first.
  That is how the Tartu layer was found.

## Repository

- Remote: `https://github.com/Ltz-lab/death-register`, private. It is meant to
  move to the BJOC-ENGINEERING account once that account's `gh` login is fixed.
- Keep it private while `data/haudi/` and the README recording are in it: the
  first was collected against a portal's terms and the second shows real
  people's names and dates.
- Related site, for comparison only: `surmaregister.ee`, a friend's listing of
  the same death records with no burial data.
