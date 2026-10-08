"""Join scraped burial rows to the death register and report how well they line up.

Reads data/haudi/rows.jsonl and the raw register files. A burial row is matched
to a register record of the same surname by the strictest rule that fits:

  exact       first name, birth date and death date all equal
  dates       birth and death dates equal, first name spelled differently
  name+death  first name and death date equal, birth date missing on one side
  name+birth  first name and birth date equal, same death year
  name+years  first name equal, same birth year and death year

Writes data/haudi/joined.jsonl (one line per burial row, with the matched
register record when there is one).
"""
import collections
import csv
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "haudi"
REGISTER_START = "1926-07-01"
TIERS = ("exact", "dates", "name+death", "name+birth", "name+years")


def first_name(value):
    return re.sub(r"\s*-\s*", "-", re.sub(r"\s+", " ", value.upper())).strip()


def iso(value):
    """dd.mm.yyyy -> yyyy-mm-dd, yyyy -> yyyy, anything else -> ''."""
    value = value.strip()
    full = re.fullmatch(r"(\d\d)\.(\d\d)\.(\d{4})", value)
    if full:
        return f"{full.group(3)}-{full.group(2)}-{full.group(1)}"
    return value if re.fullmatch(r"\d{4}", value) else ""


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


def match(row, candidates):
    first, born, died = row["first"], row["born"], row["died"]
    full_born, full_died = len(born) == 10, len(died) == 10
    best = None
    for candidate in candidates:
        same_name = first and candidate["first"] == first
        c_born, c_died = candidate["born"], candidate["died"]
        if full_born and full_died and c_born == born and c_died == died:
            tier = 0 if same_name else 1
        elif same_name and full_died and c_died == died and (not born or not c_born or born[:4] == c_born[:4]):
            tier = 2
        elif same_name and full_born and c_born == born and died[:4] == c_died[:4] and died:
            tier = 3
        elif same_name and born and died and born[:4] == c_born[:4] and died[:4] == c_died[:4]:
            tier = 4
        else:
            continue
        if best is None or tier < best[0]:
            best = (tier, candidate)
    return best


def main():
    done = {}
    for line in (OUT / "done.jsonl").read_text(encoding="utf-8").splitlines():
        entry = json.loads(line)
        done[entry["term"]] = entry
    register = load_register()

    seen = set()
    burials = []
    for line in (OUT / "rows.jsonl").read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        key = (row["burial_place"], row["name"], row["born"], row["died"], row["buried"])
        if key in seen:
            continue
        seen.add(key)
        surname = row["term"].upper()
        name = row["name"]
        if name.upper().endswith(surname):
            name = name[: len(name) - len(surname)]
        burials.append({**row, "surname": surname, "first": first_name(name),
                        "born": iso(row["born"]), "died": iso(row["died"]), "buried": iso(row["buried"])})

    tiers = collections.Counter()
    in_scope = out_of_scope = undated = 0
    matched_register = collections.defaultdict(set)
    cemeteries = collections.Counter()
    misses = []
    with open(OUT / "joined.jsonl", "w", encoding="utf-8") as out:
        for row in burials:
            cemeteries[row["cemetery"]] += 1
            found = match(row, register.get(row["surname"], ()))
            died = row["died"]
            if not died:
                undated += 1
            elif died < REGISTER_START[: len(died)]:
                out_of_scope += 1
            else:
                in_scope += 1
                if found:
                    tiers[TIERS[found[0]]] += 1
                elif len(misses) < 12 and len(died) == 10:
                    misses.append(row)
            if found:
                matched_register[row["surname"]].add((found[1]["first"], found[1]["born"], found[1]["died"]))
            out.write(json.dumps({**row, "match": TIERS[found[0]] if found else None,
                                  "register": found[1] if found else None}, ensure_ascii=False) + "\n")

    complete = [term.upper() for term, entry in done.items() if entry["complete"]]
    register_total = sum(len(register.get(s, ())) for s in complete)
    register_hit = sum(len(matched_register.get(s, ())) for s in complete)
    matched = sum(tiers.values())

    print(f"terms searched       {len(done):,} ({len(complete):,} complete)")
    print(f"burial rows          {len(burials):,} across {len(cemeteries)} cemeteries")
    print(f"  died before July 1926  {out_of_scope:,}")
    print(f"  no death date          {undated:,}")
    print(f"  died in register era   {in_scope:,}")
    print(f"matched to the register  {matched:,} of {in_scope:,} ({matched / max(in_scope, 1):.0%})")
    for tier in TIERS:
        print(f"  {tier:<11} {tiers[tier]:,}")
    print(f"register records for the complete surnames  {register_total:,}")
    print(f"  with a burial found    {register_hit:,} ({register_hit / max(register_total, 1):.0%})")
    print("largest cemeteries:", ", ".join(f"{name} {count}" for name, count in cemeteries.most_common(6)))
    print("register-era burials with no match (sample):")
    for row in misses:
        print(f"  {row['name']:<32} {row['born'] or '-':<11} {row['died']:<11} {row['cemetery']}")


if __name__ == "__main__":
    main()
