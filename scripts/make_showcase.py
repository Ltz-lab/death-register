"""Render docs/showcase.mp4: the Tartu and Saaremaa graves appearing on a map.

    uv run --python 3.12 --with numpy --with pillow scripts/make_showcase.py

Needs numpy, Pillow and ffmpeg, unlike the other scripts. Reads the two
joined.jsonl files (run join_burials.py first), draws every plot as a dot, and
plays the burials in year by year: amber where the burial matched a death
record, slate where it did not. Headstone photos for the four example cards
are fetched from Saaremaa's layer once and kept in data/showcase/.
"""
import argparse
import io
import json
import math
import pathlib
import subprocess
import urllib.request

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = pathlib.Path(__file__).resolve().parent.parent
CACHE = ROOT / "data" / "showcase"
OUT = ROOT / "docs" / "showcase.mp4"
W, H, FPS = 1280, 720, 30
MAP_X, MAP_Y = W * 0.57, H * 0.53  # where the centre of a view lands on screen
FIRST, LAST = 1926, 2026

BG = np.array((11, 14, 20), dtype=np.float32)
SLATE = np.array((72, 86, 112), dtype=np.float32)
AMBER = np.array((255, 176, 66), dtype=np.float32)
WHITE = np.array((255, 255, 255), dtype=np.float32)
TEXT, DIM = (236, 239, 244), (138, 148, 166)

FONTS = "/System/Library/Fonts/Supplemental/"


def font(size, bold=False):
    return ImageFont.truetype(FONTS + ("Arial Bold.ttf" if bold else "Arial.ttf"), size)


def ease(t):
    t = min(1.0, max(0.0, t))
    return t * t * (3 - 2 * t)


class Region:
    def __init__(self, folder, title, credit, focus, focus_title):
        lon, lat, year, matched, self.cemetery, plot = [], [], [], [], [], []
        for line in open(ROOT / "data" / folder / "joined.jsonl", encoding="utf-8"):
            row = json.loads(line)
            if row.get("lat") is None:
                continue
            when = (row["buried"] or row["died"])[:4]
            lon.append(row["lon"])
            lat.append(row["lat"])
            year.append(int(when) if when else 0)
            matched.append(bool(row["match"]))
            self.cemetery.append(row["cemetery"])
            plot.append(row["plot"] or "")
        lat0 = sum(lat) / len(lat)
        self.x = (np.array(lon) - sum(lon) / len(lon)) * math.cos(math.radians(lat0)) * 111320
        self.y = (np.array(lat) - lat0) * 110574
        self.year = np.array(year)
        self.matched = np.array(matched)
        self.title, self.credit, self.focus_title = title, credit, focus_title
        self.in_focus = np.array([focus(c, p) for c, p in zip(self.cemetery, plot)])
        self.overview = self.fit(np.ones(len(lon), dtype=bool), 0.60, 0.74)
        self.closeup = self.fit(self.in_focus, 0.62, 0.80)
        self.labels = self.cemetery_labels()

    def fit(self, mask, wide, tall):
        xs, ys = self.x[mask], self.y[mask]
        x0, x1 = np.percentile(xs, (0.5, 99.5))
        y0, y1 = np.percentile(ys, (0.5, 99.5))
        return (x0 + x1) / 2, (y0 + y1) / 2, max((x1 - x0) / (W * wide), (y1 - y0) / (H * tall))

    def cemetery_labels(self):
        names = np.array(self.cemetery)
        found = []
        for name in sorted(set(self.cemetery), key=lambda n: -(names == n).sum())[:9]:
            mask = names == name
            short = name.replace("Tartu ", "").replace(" kalmistu", "")
            found.append((short, self.x[mask].mean(), self.y[mask].mean(), int(mask.sum())))
        return found

    def screen(self, view):
        cx, cy, scale = view
        return MAP_X + (self.x - cx) / scale, MAP_Y - (self.y - cy) / scale


def stamp(buffer, px, py, colours, size):
    keep = (px > -size) & (px < W + size) & (py > -size) & (py < H + size)
    ix, iy, colours = px[keep].astype(np.int32), py[keep].astype(np.int32), colours[keep]
    half = size // 2
    for dy in range(-half, size - half):
        for dx in range(-half, size - half):
            x, y = ix + dx, iy + dy
            ok = (x >= 0) & (x < W) & (y >= 0) & (y < H)
            buffer[y[ok], x[ok]] = colours[ok]


def draw_map(region, view, born=None, frame=None, smallest=2):
    """Dots for every plot; with `born`, only those whose frame has come, newest flashing white."""
    buffer = np.empty((H, W, 3), dtype=np.float32)
    buffer[:] = BG
    px, py = region.screen(view)
    size = int(min(8, max(smallest, 2.4 / view[2])))
    colours = np.where(region.matched[:, None], AMBER, SLATE)
    shown = np.ones(len(px), dtype=bool) if born is None else born <= frame
    for layer in (~region.matched, region.matched):
        pick = shown & layer
        stamp(buffer, px[pick], py[pick], colours[pick], size)
    if born is not None:
        age = frame - born
        fresh = shown & (age < 9)
        glow = (age[fresh] / 9.0)[:, None]
        stamp(buffer, px[fresh], py[fresh], WHITE * (1 - glow) + colours[fresh] * glow, size + 1)
    return buffer


def heading(draw, region, line):
    draw.text((48, 40), region.title, font=font(54, True), fill=TEXT)
    draw.text((50, 104), line, font=font(21), fill=DIM)


def legend(draw, y=H - 74):
    for i, (colour, label) in enumerate(((AMBER, "matched to a death record"), (SLATE, "no match yet"))):
        draw.ellipse((50, y + i * 28, 62, y + 12 + i * 28), fill=tuple(int(c) for c in colour))
        draw.text((74, y - 4 + i * 28), label, font=font(18), fill=DIM)


def place_labels(draw, region, view, strength=1.0):
    taken = []
    for name, x, y, count in region.labels:
        sx = MAP_X + (x - view[0]) / view[2] + 16
        sy = MAP_Y - (y - view[1]) / view[2] - 10
        if any(abs(sy - ty) < 22 and abs(sx - tx) < 190 for tx, ty in taken) or not (300 < sx < W - 200):
            continue
        taken.append((sx, sy))
        shade = tuple(int(BG[i] + (c - BG[i]) * strength) for i, c in enumerate(TEXT))
        draw.text((sx, sy), f"{name}  {count:,}", font=font(16), fill=shade)


def region_scene(region):
    total, matched = len(region.x), int(region.matched.sum())
    grow = 9 * FPS
    born = np.clip((region.year - FIRST) / (LAST - FIRST), 0, 1) * (grow - 1)
    born_sorted, born_matched = np.sort(born), np.sort(born[region.matched])

    for f in range(3 * FPS):  # everything at once, whole region
        image = Image.fromarray(draw_map(region, region.overview, smallest=4).astype(np.uint8))
        draw = ImageDraw.Draw(image)
        heading(draw, region, region.credit)
        place_labels(draw, region, region.overview)
        draw.text((48, 150), f"{total:,}", font=font(40, True), fill=TEXT)
        draw.text((50, 196), "graves with a position", font=font(19), fill=DIM)
        draw.text((48, 236), f"{matched:,}", font=font(40, True), fill=tuple(int(c) for c in AMBER))
        draw.text((50, 282), "matched to a death record", font=font(19), fill=DIM)
        legend(draw)
        yield image, min(1.0, f / 12)

    for f in range(2 * FPS):  # push in on the largest cemetery
        t = ease(f / (2 * FPS - 1))
        a, b = region.overview, region.closeup
        view = (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, math.exp(math.log(a[2]) + (math.log(b[2]) - math.log(a[2])) * t))
        image = Image.fromarray(draw_map(region, view, smallest=4 if t < 0.5 else 2).astype(np.uint8))
        draw = ImageDraw.Draw(image)
        heading(draw, region, region.credit)
        place_labels(draw, region, view, 1 - t)
        legend(draw)
        yield image, 1.0 if f < 2 * FPS - 10 else (2 * FPS - 1 - f) / 10

    for f in range(grow + int(1.5 * FPS)):  # the same ground, filled in year by year
        frame = min(f, grow - 1)
        image = Image.fromarray(draw_map(region, region.closeup, born, frame).astype(np.uint8))
        draw = ImageDraw.Draw(image)
        heading(draw, region, region.focus_title)
        year = FIRST + round((LAST - FIRST) * frame / (grow - 1))
        draw.text((W - 48, 36), str(year), font=font(84, True), fill=TEXT, anchor="ra")
        draw.text((48, 150), f"{int(np.searchsorted(born_sorted, frame, 'right')):,}", font=font(40, True), fill=TEXT)
        draw.text((50, 196), f"{region.title.title()} graves so far", font=font(19), fill=DIM)
        draw.text((48, 236), f"{int(np.searchsorted(born_matched, frame, 'right')):,}", font=font(40, True),
                  fill=tuple(int(c) for c in AMBER))
        draw.text((50, 282), "matched to a death record", font=font(19), fill=DIM)
        legend(draw)
        last = grow + int(1.5 * FPS) - 1
        yield image, min(1.0, f / 10, (last - f) / 10 + 0.001)


def text_scene(lines, seconds):
    frames = int(seconds * FPS)
    for f in range(frames):
        image = Image.new("RGB", (W, H), tuple(int(c) for c in BG))
        draw = ImageDraw.Draw(image)
        y = H / 2 - sum(gap for _, _, _, gap in lines) / 2
        for words, face, colour, gap in lines:
            draw.text((W / 2, y), words, font=face, fill=colour, anchor="ma")
            y += gap
        yield image, min(1.0, f / 14, (frames - 1 - f) / 14 + 0.001)


def example_cards():
    """One exact match with a headstone photo from each of Saaremaa's four largest cemeteries."""
    rows = [json.loads(line) for line in open(ROOT / "data" / "saaremaa" / "joined.jsonl", encoding="utf-8")]
    sizes = {}
    for row in rows:
        sizes[row["cemetery"]] = sizes.get(row["cemetery"], 0) + 1
    CACHE.mkdir(parents=True, exist_ok=True)
    for cemetery in sorted(sizes, key=sizes.get, reverse=True)[:4]:
        fits = [r for r in rows if r["cemetery"] == cemetery and r["match"] == "exact" and r.get("photo")
                and r["lat"] is not None and r["buried"] and "1955" <= r["died"] <= "2015"]
        row = fits[len(fits) // 2]
        cached = CACHE / f"{row['source_id']}.jpg"
        if not cached.exists():
            request = urllib.request.Request(row["photo"], headers={"User-Agent": "death-register/0.1"})
            with urllib.request.urlopen(request, timeout=120) as response:
                cached.write_bytes(response.read())
        photo = ImageOps.exif_transpose(Image.open(io.BytesIO(cached.read_bytes()))).convert("RGB")
        yield row, ImageOps.fit(photo, (520, 520))


def card_scene(row, photo):
    person = row["register"]
    amber = tuple(int(c) for c in AMBER)
    facts = (("Death register", "matched on name, birth date and death date", amber),
             ("Cemetery", row["cemetery"], TEXT), ("Plot", row["plot"], TEXT),
             ("Buried", ".".join(reversed(row["buried"].split("-"))), TEXT),
             ("Position", f"{row['lat']:.5f}, {row['lon']:.5f}", TEXT))
    frames = int(2.8 * FPS)
    for f in range(frames):
        image = Image.new("RGB", (W, H), tuple(int(c) for c in BG))
        image.paste(photo, (70, 100))
        draw = ImageDraw.Draw(image)
        draw.text((650, 118), f"{person['first']} {person['surname']}".title(), font=font(46, True), fill=TEXT)
        draw.text((652, 180), f"{person['born'][:4]} – {person['died'][:4]}", font=font(30), fill=DIM)
        for i, (label, value, colour) in enumerate(facts):
            draw.text((652, 262 + i * 66), label.upper(), font=font(15, True), fill=DIM)
            draw.text((652, 284 + i * 66), value, font=font(24), fill=colour)
        draw.text((70, 640), "Headstone photo: Saaremaa municipality", font=font(15), fill=DIM)
        yield image, min(1.0, f / 10, (frames - 1 - f) / 10 + 0.001)


def scenes():
    deaths = sum(sum(1 for _ in open(path, "rb")) - 1 for path in sorted((ROOT / "data" / "raw").glob("surmaandmed_*.csv")))
    tartu = Region("tartu", "TARTU", "15 cemeteries, published by Tartu City Government",
                   lambda cemetery, plot: plot.startswith("RAD"), "Raadi cemeteries, 1926 to today")
    saaremaa = Region("saaremaa", "SAAREMAA", "33 cemeteries, published by Saaremaa municipality",
                      lambda cemetery, plot: cemetery == "Kudjape", "Kudjape cemetery, 1926 to today")
    amber = tuple(int(c) for c in AMBER)
    yield from text_scene(((f"{deaths:,} deaths on record.", font(58, True), TEXT, 84),
                           ("Where are they buried?", font(58, True), amber, 110),
                           ("Estonia's open death register, joined to open cemetery data", font(22), DIM, 30)), 3.6)
    yield from region_scene(tartu)
    yield from region_scene(saaremaa)
    for row, photo in example_cards():
        yield from card_scene(row, photo)
    found = [int(r.matched.sum()) for r in (tartu, saaremaa)]
    yield from text_scene(((f"{sum(found):,}", font(110, True), amber, 132),
                           ("graves on the map, matched to a death record", font(34), TEXT, 74),
                           (f"Tartu {found[0]:,}   ·   Saaremaa {found[1]:,}", font(24), DIM, 86),
                           ("github.com/Ltz-lab/death-register", font(24, True), TEXT, 54),
                           ("Data: Ministry of the Interior of Estonia (CC BY 4.0), Tartu City Government, "
                            "Saaremaa municipality", font(15), DIM, 20)), 5)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--stills", help="write these frame numbers as PNGs into this folder instead: DIR:N,N,N")
    args = parser.parse_args()
    background = Image.new("RGB", (W, H), tuple(int(c) for c in BG))
    stills = None
    encoder = None
    if args.stills:
        folder, numbers = args.stills.split(":")
        stills = (pathlib.Path(folder), {int(n) for n in numbers.split(",")})
    else:
        OUT.parent.mkdir(exist_ok=True)
        encoder = subprocess.Popen(
            ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
             "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "-movflags", "+faststart", str(OUT)],
            stdin=subprocess.PIPE)
    count = 0
    for image, alpha in scenes():
        if stills is None or count in stills[1]:
            if alpha < 1:
                image = Image.blend(background, image, max(0.0, alpha))
            if stills:
                image.save(stills[0] / f"frame_{count:05d}.png")
            else:
                encoder.stdin.write(image.tobytes())
        count += 1
    if encoder:
        encoder.stdin.close()
        encoder.wait()
        print(f"{count} frames, {count / FPS:.1f}s -> {OUT}")
    else:
        print(f"{count} frames in total")


if __name__ == "__main__":
    main()
