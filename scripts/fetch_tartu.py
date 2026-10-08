"""Download Tartu's public burial layer.

Tartu City Government publishes its cemeteries on the national open data portal
(andmed.eesti.ee, "Tartu kalmistute kaardirakendus", CC BY-SA 3.0) as an ArcGIS
feature service. The public layer KA_avalik_maetu holds one polygon per burial:
name, birth, death and burial dates, plot code and cemetery. This pages through
it and writes data/tartu/rows.jsonl with each plot's centre in WGS84.
"""
import datetime
import json
import pathlib
import time
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "tartu"
LAYER = "https://gis.tartulv.ee/arcgis/rest/services/Kalmistu/KA_avalik_maetu/FeatureServer/0/query"
PAGE = 10000
EPOCH = datetime.datetime(1970, 1, 1)


def day(milliseconds):
    if milliseconds is None:
        return ""
    return (EPOCH + datetime.timedelta(milliseconds=milliseconds)).date().isoformat()


def query(offset):
    params = urllib.parse.urlencode({
        "where": "1=1", "outFields": "*", "orderByFields": "OBJECTID",
        "returnGeometry": "false", "returnCentroid": "true", "outSR": "4326",
        "resultOffset": offset, "resultRecordCount": PAGE, "f": "json",
    })
    request = urllib.request.Request(f"{LAYER}?{params}", headers={"User-Agent": "death-register/0.1"})
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.load(response)


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
                out.write(json.dumps({
                    "source_id": a["GlobalID"],
                    "first": (a["E_nimi"] or "").strip(),
                    "surname": (a["P_nimi"] or "").strip(),
                    "name": (a["Maetu_nimi"] or "").strip(),
                    "born": day(a["Sy_aeg"]),
                    "died": day(a["Su_aeg"]),
                    "buried": day(a["Ma_aeg"]),
                    "plot": a["P_kood"],
                    "cemetery": a["Nimi"],
                    "lat": centre.get("y"),
                    "lon": centre.get("x"),
                }, ensure_ascii=False) + "\n")
            count += len(features)
            print(f"{count:,} rows", flush=True)
            if len(features) < PAGE:
                break
            offset += PAGE
            time.sleep(1)
    print(f"wrote {OUT / 'rows.jsonl'}")


if __name__ == "__main__":
    main()
