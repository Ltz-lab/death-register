"""Print matched people and their graves from a matches.csv, one per line.

    python3 -I scripts/show_matches.py data/tartu/matches.csv --match exact --limit 40

Rows are taken at even steps through the file so the sample spans the alphabet.
"""
import argparse
import csv
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("matches", help="a matches.csv written by join_burials.py")
    parser.add_argument("--match", help="only rows paired by this rule, e.g. exact")
    parser.add_argument("--limit", type=int, default=40)
    parser.add_argument("--delay", type=float, default=0, help="seconds to pause between rows")
    args = parser.parse_args()

    with open(args.matches, encoding="utf-8", newline="") as handle:
        rows = [row for row in csv.DictReader(handle) if not args.match or row["match"] == args.match]
    step = max(1, len(rows) // args.limit)
    print(f"{'NAME':<28} {'LIVED':<9}  {'BURIED':<10}  {'CEMETERY':<26} {'PLOT':<13} POSITION")
    for row in rows[::step][: args.limit]:
        name = f"{row['first_name']} {row['surname']}".title()
        lived = f"{row['born'][:4] or '?'}-{row['died'][:4]}"
        place = f"{float(row['lat']):.5f}, {float(row['lon']):.5f}" if row["lat"] else ""
        print(f"{name[:28]:<28} {lived:<9}  {row['buried'] or '-':<10}  {row['cemetery'][:26]:<26} "
              f"{row['plot'][:13]:<13} {place}", flush=True)
        if args.delay:
            time.sleep(args.delay)
    print(f"\n{len(rows):,} matches in {args.matches}")


if __name__ == "__main__":
    main()
