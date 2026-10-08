"""Collect burial rows from kalmistud.ee (the Haudi cemetery register).

The portal only lists burials through its name search: a surname (exact, or
three or more letters matched anywhere), 20 rows a page, with the search held
in the session. This walks a list of terms one request at a time, appends
each row to data/haudi/rows.jsonl and records finished terms in
data/haudi/done.jsonl so a rerun carries on where it stopped.

It stops on a 403/429 or a captcha page and does not try to get round them.
"""
import argparse
import html
import http.cookiejar
import json
import pathlib
import random
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "haudi"
BASE = "https://www.kalmistud.ee"
SEARCH = "/search/deceased"
AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"

TOKEN = re.compile(r'name="deceased_filter\[_token\]" value="([^"]*)"')
FOUND = re.compile(r"Leiti\s+(\d+)\s+kirjet")
LAST_PAGE = re.compile(r'data-url="/search/deceased\?page=(\d+)"\s*title="Viimane')
ROW = re.compile(r"<tr>(.*?)</tr>", re.S)
CELL = re.compile(r"<td>(.*?)</td>", re.S)
TAG = re.compile(r"<[^>]+>")
BLOCKED = re.compile(r"captcha|recaptcha|turnstile", re.I)


class Stop(Exception):
    pass


class Portal:
    def __init__(self, delay):
        jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
        self.opener.addheaders = [("User-Agent", AGENT)]
        self.delay = delay
        self.last = 0.0
        self.requests = 0
        self.token = None

    def fetch(self, path, data=None):
        wait = self.last + self.delay * random.uniform(0.85, 1.15) - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        self.last = time.monotonic()
        self.requests += 1
        body = urllib.parse.urlencode(data).encode() if data else None
        for attempt in range(4):
            try:
                with self.opener.open(BASE + path, data=body, timeout=60) as response:
                    page = response.read().decode("utf-8", "replace")
                break
            except urllib.error.HTTPError as error:
                if error.code in (403, 429):
                    raise Stop(f"HTTP {error.code} on {path}: the portal is refusing requests")
                if attempt == 3:
                    raise Stop(f"HTTP {error.code} on {path} after 4 tries")
            except (urllib.error.URLError, TimeoutError, ConnectionError) as error:
                if attempt == 3:
                    raise Stop(f"network error on {path}: {error}")
            time.sleep(10 * (attempt + 1))
        if BLOCKED.search(page):
            raise Stop(f"captcha page on {path}")
        token = TOKEN.search(page)
        if token:
            self.token = html.unescape(token.group(1))
        return page

    def search(self, term, mode):
        if not self.token:
            self.fetch(SEARCH)
        if not self.token:
            raise Stop("no form token on the search page")
        prefix = "deceased_filter"
        form = {
            f"{prefix}[searchMode][]": "deceased",
            f"{prefix}[searchType]": mode,
            f"{prefix}[firstName]": "",
            f"{prefix}[lastName]": term,
            f"{prefix}[burialPlaceAddress]": "",
            f"{prefix}[birthDate][from]": "",
            f"{prefix}[birthDate][to]": "",
            f"{prefix}[deathDate][from]": "",
            f"{prefix}[deathDate][to]": "",
            f"{prefix}[burialDate][from]": "",
            f"{prefix}[burialDate][to]": "",
            f"{prefix}[activeCemeteryId]": "0",
            f"{prefix}[_token]": self.token,
            "search-deceased": "Otsin maetut",
        }
        return self.fetch(SEARCH, form)


def text(cell):
    return re.sub(r"\s+", " ", html.unescape(TAG.sub(" ", cell))).strip()


def link(cell, pattern):
    found = re.search(pattern, cell)
    return found.group(1) if found else None


def rows(page):
    for block in ROW.findall(page):
        cells = CELL.findall(block)
        if len(cells) != 7:
            continue
        plan = re.search(r'href="/plan/(\d+)/(\d+)"', cells[6])
        yield {
            "name": text(cells[0]),
            "born": text(cells[1]),
            "died": text(cells[2]),
            "buried": text(cells[3]),
            "plot": text(cells[4]),
            "cemetery": text(cells[5]),
            "cemetery_id": link(cells[5], r'href="/cemetery/(\d+)"'),
            "burial_place": link(cells[0], r'href="/burial-place/([^"]+)"'),
            "plot_id": plan.group(2) if plan else None,
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("terms", help="file with one surname or name piece per line")
    parser.add_argument("--mode", choices=("tapne", "osa"), default="osa", help="tapne = exact surname, osa = part of surname")
    parser.add_argument("--minutes", type=float, default=0, help="stop after this long (0 = run to the end)")
    parser.add_argument("--delay", type=float, default=1.3, help="seconds between request starts")
    parser.add_argument("--max-pages", type=int, default=0, help="per term; a term cut short is recorded as incomplete")
    args = parser.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    done_path = OUT / "done.jsonl"
    done = set()
    if done_path.exists():
        for line in done_path.read_text(encoding="utf-8").splitlines():
            entry = json.loads(line)
            done.add((entry["term"], entry["mode"]))
    terms = [t.strip() for t in pathlib.Path(args.terms).read_text(encoding="utf-8").splitlines() if t.strip()]
    deadline = time.monotonic() + args.minutes * 60 if args.minutes else None
    portal = Portal(args.delay)
    saved = 0
    finished = 0
    try:
        with open(OUT / "rows.jsonl", "a", encoding="utf-8") as out, open(done_path, "a", encoding="utf-8") as log:
            for term in terms:
                if (term, args.mode) in done:
                    continue
                if deadline and time.monotonic() > deadline:
                    break
                page = portal.search(term, args.mode)
                found = FOUND.search(page)
                total = int(found.group(1)) if found else 0
                last = LAST_PAGE.search(page)
                pages = int(last.group(1)) if last else 1
                fetched = 0
                number = 1
                while True:
                    for row in rows(page):
                        row["term"] = term
                        out.write(json.dumps(row, ensure_ascii=False) + "\n")
                        fetched += 1
                    if number >= pages or (args.max_pages and number >= args.max_pages):
                        break
                    if deadline and time.monotonic() > deadline:
                        break
                    number += 1
                    page = portal.fetch(f"{SEARCH}?page={number}")
                out.flush()
                complete = number >= pages
                log.write(json.dumps({"term": term, "mode": args.mode, "total": total, "rows": fetched,
                                      "complete": complete}, ensure_ascii=False) + "\n")
                log.flush()
                saved += fetched
                finished += 1
    except Stop as stop:
        print(f"stopped: {stop}", file=sys.stderr)
    print(f"{finished} terms, {saved} rows, {portal.requests} requests")


if __name__ == "__main__":
    main()
