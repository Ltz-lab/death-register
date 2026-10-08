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

**Burials.** [kalmistud.ee](https://www.kalmistud.ee) is the Haudi cemetery
register: about 234 cemeteries whose municipalities entered their cemetery books
and headstone inventories. It has no bulk download. Its terms of service forbid
automated collection.

## Scripts

Standard-library Python 3.9+, no dependencies. Run them with `python3 -I`.

| Script | What it does |
|---|---|
| `scripts/haudi_cover.py` | Picks the surname search terms that reach every surname in the death register in the fewest result pages. Writes `data/haudi/terms.txt`. |
| `scripts/scrape_haudi.py` | Walks a list of terms through the portal's name search, one request at a time, and appends rows to `data/haudi/rows.jsonl`. Resumable; stops on a block or captcha. |
| `scripts/haudi_join.py` | Matches burial rows to death records by surname, first name and dates, and prints the match rates. Writes `data/haudi/joined.jsonl`. |

```sh
python3 -I scripts/scrape_haudi.py data/haudi/poc_terms.txt --mode tapne --minutes 10 --max-pages 40
python3 -I scripts/haudi_join.py
```
