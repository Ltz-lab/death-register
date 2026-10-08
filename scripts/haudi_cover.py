"""Pick the search terms for the kalmistud.ee scrape.

The portal's partial-name search needs three or more letters and matches them
anywhere in the surname. The death register's surnames stand in for the
portal's: a greedy set cover picks 3- to 5-letter windows and whole surnames so
every surname is matched by some term in the fewest result pages.
Writes data/haudi/terms.txt, one term per line, best value first.
"""
import csv
import heapq
import collections
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "haudi" / "terms.txt"
LETTERS = re.compile(r"^[^\W\d_]+$")
PAGE = 20


def surnames():
    counts = collections.Counter()
    for path in sorted(RAW.glob("surmaandmed_*.csv")):
        with open(path, encoding="utf-8-sig", newline="") as handle:
            reader = csv.reader(handle, delimiter=";", quotechar='"')
            next(reader)
            for row in reader:
                if len(row) == 5 and row[1] not in ("", "-"):
                    counts[row[1].lower()] += 1
    return counts


def windows(name):
    """Every searchable piece of a surname: 3- to 5-letter windows and the whole name."""
    out = set()
    for size in (3, 4, 5):
        for i in range(len(name) - size + 1):
            piece = name[i:i + size]
            if LETTERS.match(piece):
                out.add(piece)
    if len(name) >= 3 and "%" not in name and "_" not in name:
        out.add(name)
    return out


def pages(rows):
    return max(1, -(-rows // PAGE))


def main():
    counts = surnames()
    members = collections.defaultdict(list)
    short = []
    for name in counts:
        ws = windows(name)
        if not ws:
            short.append(name)
        for w in ws:
            members[w].append(name)
    # A whole-name term also returns every longer surname containing it.
    weight = {w: sum(counts[n] for n in names) for w, names in members.items()}
    for w in list(members):
        if len(w) > 5:
            weight[w] = sum(counts[n] for n in counts if w in n) if len(members[w]) == 1 and counts[w] > 200 else weight[w]
    covered = set()
    heap = [(-weight[w] / pages(weight[w]), w) for w in members]
    heapq.heapify(heap)
    chosen = []
    todo = sum(1 for n in counts if n not in short)
    while len(covered) < todo and heap:
        _, w = heapq.heappop(heap)
        gain = sum(counts[n] for n in members[w] if n not in covered)
        if gain == 0:
            continue
        score = -gain / pages(weight[w])
        if heap and score > heap[0][0]:
            heapq.heappush(heap, (score, w))
            continue
        chosen.append(w)
        covered.update(members[w])
    returned = sum(weight[w] for w in chosen)
    total = sum(counts.values())
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(chosen) + "\n", encoding="utf-8")
    print(f"surnames {len(counts):,}  records {total:,}")
    print(f"terms {len(chosen):,}  rows returned {returned:,}  overhead {returned / total:.2f}x")
    print(f"est. requests {sum(pages(weight[w]) for w in chosen):,}")
    print(f"surnames with no 3-letter window: {len(short)}")
    print("largest terms", sorted(((weight[w], w) for w in chosen), reverse=True)[:8])
    print("by length", sorted(collections.Counter(min(len(w), 6) for w in chosen).items()))


if __name__ == "__main__":
    main()
