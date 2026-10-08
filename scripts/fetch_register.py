"""Download the Ministry of the Interior's open death records into data/raw/.

Source: https://andmed.eesti.ee/datasets/surmaandmed (CC BY 4.0). The files are
regenerated every day, so each run replaces the previous copy.
"""
import pathlib
import shutil
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
BASE = "https://opendata.smit.ee/etl/rahvastik/"
FILES = (
    "surmaandmed_1926_kuni_eelmise_aasta_lopuni.csv",
    "surmaandmed_jooksev_aasta.csv",
)


def main():
    RAW.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        request = urllib.request.Request(BASE + name, headers={"User-Agent": "death-register/0.1"})
        with urllib.request.urlopen(request, timeout=300) as response, open(RAW / name, "wb") as out:
            shutil.copyfileobj(response, out)
        print(f"{name}  {(RAW / name).stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
