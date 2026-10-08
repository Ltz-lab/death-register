# death-register

Estonia's open death records, joined to where people are buried.

![Matching Tartu burials to the death register](docs/records.gif)

| | |
|---|---|
| Death records (Ministry of the Interior, open data) | 1,732,767 |
| Tartu burials with coordinates (open data) | 84,193 |
| Tartu burials matched to a death record | 49,001 |
| kalmistud.ee burials matched, before it blocked us | 946 of 1,548 fetched |

## Data

| File | Contents |
|---|---|
| `data/tartu/matches.csv` | Name, birth and death dates, burial date, cemetery, plot, coordinates |
| `data/tartu/rows.jsonl` | Every Tartu burial as published |
| `data/haudi/` | The kalmistud.ee proof of concept |

The death records (97 MB) are downloaded, not committed.

## Run

```sh
python3 -I scripts/fetch_register.py
python3 -I scripts/fetch_tartu.py
python3 -I scripts/join_burials.py data/tartu/rows.jsonl
python3 -I scripts/show_matches.py data/tartu/matches.csv --match exact
```

Python 3.9+, no dependencies.

Sources, what was tried, match rules and open questions: [docs/notes.md](docs/notes.md).
