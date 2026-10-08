"""Download Saaremaa's public burial layer, printing rows as they arrive.

Saaremaa municipality runs the same cemetery system as Tartu and exposes the
same public layer, Kalmistud/KA_avalik_maetu: one polygon per burial with name,
birth, death and burial dates, plot code, cemetery and a headstone photo link.
Writes data/saaremaa/rows.jsonl with each plot's centre in WGS84.
"""
import json
import pathlib
import time
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "saaremaa"
LAYER = "https://gis.saaremaavald.ee/arcgis/rest/services/Kalmistud/KA_avalik_maetu/FeatureServer/0/query"
PAGE = 1000


def query(offset):
    params = urllib.parse.urlencode({
        "where": "1=1", "outFields": "*", "orderByFields": "objectid",
        "returnGeometry": "false", "returnCentroid": "true", "outSR": "4326",
        "resultOffset": offset, "resultRecordCount": PAGE, "f": "json",
    })
    request = urllib.request.Request(f"{LAYER}?{params}", headers={"User-Agent": "death-register/0.1"})
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.load(response)


def clean(value):
    return " ".join((value or "").split())


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    count = 0
    with open(OUT / "rows.jsonl", "w", encoding="utf-8") as out:
        offset = 0
        while True:
            page = query(offset)
            if "error" in page:
                raise SystemExit(f"service error: {page['error']}")
            features = page.get("features", [])
            for feature in features:
                a = feature["attributes"]
                centre = feature.get("centroid") or {}
                row = {
                    "source_id": f"saaremaa-{a['objectid']}",
                    "first": clean(a["e_nimi"]),
                    "surname": clean(a["p_nimi"]),
                    "name": clean(a["maetu_nimi"]),
                    "born": clean(a["sy_aeg"]),
                    "died": clean(a["su_aeg"]),
                    "buried": clean(a["ma_aeg"]),
                    "plot": a["p_kood"],
                    "cemetery": clean(a["nimi"]),
                    "lat": centre.get("y"),
                    "lon": centre.get("x"),
                    "photo": a.get("photo_url"),
                }
                out.write(json.dumps(row, ensure_ascii=False) + "\n")
                count += 1
                place = f"{row['lat']:.5f}, {row['lon']:.5f}" if row["lat"] is not None else ""
                print(f"{row['name'][:30]:<30} {row['born'][-4:] or '?':>4}-{row['died'][-4:] or '?':<4}  "
                      f"{row['cemetery'][:18]:<18} {str(row['plot'])[:14]:<14} {place}", flush=True)
            print(f"\033[36m  {count:,} burials\033[0m", flush=True)
            if len(features) < PAGE:
                break
            offset += PAGE
            time.sleep(1)
    print(f"wrote {OUT / 'rows.jsonl'}")


if __name__ == "__main__":
    main()
