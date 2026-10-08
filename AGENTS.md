# death-register Agent Guide

## Purpose

Join Estonia's open death records to where people are buried. `README.md` is
the short version; `docs/notes.md` has the sources, what was tried, the match
rules and the open questions.

## Project map

- `scripts/` - everything that fetches, joins and shows data. Standard-library
  Python 3.9+, no dependencies; each script runs on its own.
- `data/raw/` - the ministry's two death-record CSVs. Gitignored (97 MB);
  `scripts/fetch_register.py` downloads them.
- `data/tartu/` - Tartu's public burial layer (`rows.jsonl`) and its matches
  (`matches.csv`). Both committed.
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
| `scrape_haudi.py` | Walks terms through the kalmistud.ee name search. |

## Commands

```sh
python3 -I scripts/fetch_register.py
python3 -I scripts/fetch_tartu.py
python3 -I scripts/join_burials.py data/tartu/rows.jsonl
python3 -I scripts/join_burials.py data/haudi/rows.jsonl
python3 -I scripts/show_matches.py data/tartu/matches.csv --match exact
```

There are no tests. Rerunning the join on both sources and comparing the
printed rates with `docs/notes.md` shows whether a change moved anything.

## How the data behaves

- The ministry's CSV has five columns: first name, surname, personal ID code,
  birth date, death date. `join_burials.py` drops the ID code on load, so
  nothing under `data/tartu/` or `data/haudi/` contains one.
- The death records are regenerated daily. `fetch_register.py` overwrites the
  previous copy; nothing here keeps history yet.
- Register names are upper case; burial names are mixed case with spaces
  around hyphens. `first_name()` in `join_burials.py` puts both in one form.
- Many rows are partial: 188,668 register records have no birth date, and most
  Tartu rows have only a burial date. A missing value is `""` after loading
  (`-` in the ministry's file).
- `matches.csv` takes name and dates from the register and the burial fields
  from the cemetery. The `match` column is the rule that paired them, strictest
  first: `exact`, `dates`, `name+death`, `name+birth`, `name+burial`,
  `name+years`. `name+burial` (buried 0 to 45 days after the registered death)
  is three quarters of the Tartu matches, and its error rate on common names
  has not been measured.
- The same headline numbers appear in `README.md` and `docs/notes.md`.

## The sources

- **Death records:** `opendata.smit.ee/etl/rahvastik/`, open data, CC BY 4.0.
- **Tartu:** `gis.tartulv.ee`, layer `Kalmistu/KA_avalik_maetu`, a public
  ArcGIS feature service returning 10,000 records a request. The open-data
  listing gives CC BY-SA 3.0 for a sibling service (`KA_koond`); whether that
  covers this layer is unconfirmed. It was found by searching `andmed.eesti.ee`.
- **kalmistud.ee** (Haudi, run by AS Spin TEK): name search only, 20 rows a
  page. Its terms forbid automated collection. On 8 October 2026 it started
  refusing connections from this network about 450 requests into a test run; a
  full listing would take about 335,000 requests.
- **Saaremaa:** `saaremaavald.ee/kalmistud`, a separate system nobody has
  looked at yet.

## Repository

Remote: `https://github.com/Ltz-lab/death-register`, private. It was meant for
the BJOC-ENGINEERING account, whose `gh` login on this Mac is expired.
`surmaregister.ee` is a friend's listing of the same death records, with no
burial data.
