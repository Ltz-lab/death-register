"""Scrape surmaregister.ee's index of people, printing each month as it arrives.

The site lists every person on one page per month (/en/aasta/YYYY/MM): its own
record number, name, birth date, death date and age. Scraping every month from
July 1926 gives the whole site in about 1,200 requests, without opening the 1.7
million person pages. Writes data/surmaregister/people.jsonl and records
finished months in data/surmaregister/done.txt so a rerun carries on.

Stops on a 403 or 429.
"""
import argparse
import datetime
import html
import json
import pathlib
import re
import sys
import time
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "surmaregister"
BASE = "https://surmaregister.ee"
AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"
ROW = re.compile(
    r'<a href="/en/isik/(\d+)/([^"]+)"[^>]*>([^<]*)</a></td>'
    r'<td[^>]*>([^<]*)</td><td[^>]*>([^<]*)</td><td[^>]*>([^<]*)</td>')


def fetch(path):
    request = urllib.request.Request(BASE + path, headers={"User-Agent": AGENT})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                return response.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as error:
            if error.code == 404:
                return None
            if error.code in (403, 429):
                raise SystemExit(f"stopped: HTTP {error.code} on {path}")
            if attempt == 3:
                raise SystemExit(f"stopped: HTTP {error.code} on {path} after 4 tries")
        except OSError as error:
            if attempt == 3:
                raise SystemExit(f"stopped: {error} on {path}")
        time.sleep(10 * (attempt + 1))


def months():
    today = datetime.date.today()
    year, month = 1926, 7
    while (year, month) <= (today.year, today.month):
        yield f"{year}/{month:02d}"
        year, month = (year, month + 1) if month < 12 else (year + 1, 1)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--delay", type=float, default=1.5, help="seconds between requests")
    args = parser.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    done_path = OUT / "done.txt"
    done = set(done_path.read_text().split()) if done_path.exists() else set()
    total = 0
    with open(OUT / "people.jsonl", "a", encoding="utf-8") as out, open(done_path, "a") as log:
        for month in months():
            if month in done:
                continue
            page = fetch(f"/en/aasta/{month}")
            people = ROW.findall(page) if page else []
            for number, slug, name, born, died, age in people:
                out.write(json.dumps({
                    "id": int(number), "slug": slug, "name": html.unescape(name).strip(),
                    "born": born.strip(), "died": died.strip(), "age": age.strip(), "month": month,
                }, ensure_ascii=False) + "\n")
            out.flush()
            log.write(month + "\n")
            log.flush()
            total += len(people)
            sample = ", ".join(html.unescape(p[2]).strip().title() for p in people[:3])
            print(f"{month}  {len(people):>5,} people  {total:>9,} total   {sample[:70]}", flush=True)
            time.sleep(args.delay)
    print(f"done: {total:,} people this run -> {OUT / 'people.jsonl'}", file=sys.stderr)


if __name__ == "__main__":
    main()
