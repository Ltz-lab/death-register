"""Join burial rows to the death register and report how well they line up.

    python3 -I scripts/join_burials.py data/tartu/rows.jsonl
    python3 -I scripts/join_burials.py data/haudi/rows.jsonl

A burial row is matched to a register record of the same surname by the
strictest rule that fits:

  exact        first name, birth date and death date all equal
  dates        birth and death dates equal, first name spelled differently
  name+death   first name and death date equal, birth date missing on one side
  name+birth   first name and birth date equal, same death year
  name+burial  first name equal, buried 0 to 45 days after the registered death
  name+years   first name equal, same birth year and death year

Writes joined.jsonl beside the input: one line per burial row, with the matched
register record when there is one.
"""
import collections
import csv
import datetime
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
REGISTER_START = "1926-07-01"
TIERS = ("exact", "dates", "name+death", "name+birth", "name+burial", "name+years")
BURIAL_WINDOW = 45


def first_name(value):
    return re.sub(r"\s*-\s*", "-", re.sub(r"\s+", " ", value.upper())).strip()


def iso(value):
    """dd.mm.yyyy -> yyyy-mm-dd; yyyy-mm-dd and yyyy pass through; anything else -> ''."""
    value = (value or "").strip()
    full = re.fullmatch(r"(\d\d)\.(\d\d)\.(\d{4})", value)
    if full:
        return f"{full.group(3)}-{full.group(2)}-{full.group(1)}"
    return value if re.fullmatch(r"\d{4}(-\d\d-\d\d)?", value) else ""


def days_between(earlier, later):
    try:
        return (datetime.date.fromisoformat(later) - datetime.date.fromisoformat(earlier)).days
    except ValueError:
        return None


def load_register():
    by_surname = collections.defaultdict(list)
    for path in sorted(RAW.glob("surmaandmed_*.csv")):
        with open(path, encoding="utf-8-sig", newline="") as handle:
            reader = csv.reader(handle, delimiter=";", quotechar='"')
            next(reader)
            for row in reader:
                if len(row) != 5:
                    continue
                first, surname, _code, born, died = row
                by_surname[surname.upper()].append({
                    "first": "" if first == "-" else first_name(first),
                    "surname": surname.upper(),
                    "born": "" if born == "-" else born,
                    "died": died,
                })
    return by_surname


def load_burials(path):
    """Rows from either source, with surname, first name and ISO dates filled in."""
    seen = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        key = row.get("source_id") or (row["burial_place"], row["name"], row["born"], row["died"], row["buried"])
        if key in seen:
            continue
        seen.add(key)
        if "surname" in row:
            surname, first = row["surname"].upper(), row["first"]
        else:  # kalmistud.ee rows carry only the full name; the search term was the surname
            surname, first = row["term"].upper(), row["name"]
            if first.upper().endswith(surname):
                first = first[: len(first) - len(surname)]
        yield {**row, "surname": surname, "first": first_name(first),
               "born": iso(row["born"]), "died": iso(row["died"]), "buried": iso(row["buried"])}


def match(row, candidates):
    first, born, died, buried = row["first"], row["born"], row["died"], row["buried"]
    full_born, full_died = len(born) == 10, len(died) == 10
    best = None
    for candidate in candidates:
        same_name = first and candidate["first"] == first
        c_born, c_died = candidate["born"], candidate["died"]
        gap = 0
        if full_born and full_died and c_born == born and c_died == died:
            tier = 0 if same_name else 1
        elif same_name and full_died and c_died == died and (not born or not c_born or born[:4] == c_born[:4]):
            tier = 2
        elif same_name and full_born and c_born == born and died and died[:4] == c_died[:4]:
            tier = 3
        elif same_name and not died and len(buried) == 10 and (not born or not c_born or born[:4] == c_born[:4]):
            gap = days_between(c_died, buried)
            if gap is None or not 0 <= gap <= BURIAL_WINDOW:
                continue
            tier = 4
        elif same_name and born and died and born[:4] == c_born[:4] and died[:4] == c_died[:4]:
            tier = 5
        else:
            continue
        if best is None or (tier, gap) < best[:2]:
            best = (tier, gap, candidate)
    return best


def main():
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    path = pathlib.Path(sys.argv[1])
    register = load_register()
    burials = list(load_burials(path))

    tiers = collections.Counter()
    in_scope = out_of_scope = undated = located = 0
    matched_register = collections.defaultdict(set)
    cemeteries = collections.Counter()
    misses = []
    with open(path.with_name("joined.jsonl"), "w", encoding="utf-8") as out:
        for row in burials:
            cemeteries[row["cemetery"]] += 1
            found = match(row, register.get(row["surname"], ()))
            when = row["died"] or row["buried"]
            if not when:
                undated += 1
            elif when < REGISTER_START[: len(when)]:
                out_of_scope += 1
            else:
                in_scope += 1
                if found:
                    tiers[TIERS[found[0]]] += 1
                    located += row.get("lat") is not None
                elif len(misses) < 10 and len(when) == 10:
                    misses.append(row)
            if found:
                matched_register[row["surname"]].add((found[2]["first"], found[2]["born"], found[2]["died"]))
            out.write(json.dumps({**row, "match": TIERS[found[0]] if found else None,
                                  "register": found[2] if found else None}, ensure_ascii=False) + "\n")

    matched = sum(tiers.values())
    print(f"burial rows              {len(burials):,} across {len(cemeteries)} cemeteries")
    print(f"  before July 1926       {out_of_scope:,}")
    print(f"  no death or burial date  {undated:,}")
    print(f"  register era           {in_scope:,}")
    print(f"matched to the register  {matched:,} of {in_scope:,} ({matched / max(in_scope, 1):.0%})")
    for tier in TIERS:
        print(f"  {tier:<12} {tiers[tier]:,}")
    if located:
        print(f"matched rows with coordinates  {located:,}")

    done_path = path.with_name("done.jsonl")
    if done_path.exists():  # scraped by surname: coverage is measurable for the surnames fetched in full
        complete = []
        for line in done_path.read_text(encoding="utf-8").splitlines():
            entry = json.loads(line)
            if entry["complete"]:
                complete.append(entry["term"].upper())
        total = sum(len(register.get(s, ())) for s in complete)
        hit = sum(len(matched_register.get(s, ())) for s in complete)
        print(f"register records for the {len(complete)} complete surnames  {total:,}")
        print(f"  with a burial found    {hit:,} ({hit / max(total, 1):.0%})")
    print("largest cemeteries:", ", ".join(f"{name} {count:,}" for name, count in cemeteries.most_common(5)))
    print("register-era burials with no match (sample):")
    for row in misses:
        print(f"  {row['name']:<30} born {row['born'] or '-':<11} died {row['died'] or '-':<11} "
              f"buried {row['buried'] or '-':<11} {row['cemetery']}")


if __name__ == "__main__":
    main()
