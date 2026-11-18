"""
Download otomatis data stasiun Weathercloud (ITS Kampus Sukolilo & Keputih)
lalu simpan dalam format rapi:
  data/<Stasiun>/<Stasiun>_YYYY-MM.csv   -> CSV UTF-8, pemisah koma, desimal titik, waktu ISO
  data/<Stasiun>/<Stasiun>_YYYY-MM.xlsx  -> Excel (angka tersimpan sebagai angka, aman untuk Excel Indonesia)
  data/<Stasiun>/<Stasiun>_semua.csv     -> gabungan semua bulan

Pemakaian:
  python weathercloud_sync.py                 # update bulan berjalan (dipakai harian)
  python weathercloud_sync.py --backfill 12   # ambil 12 bulan terakhir sekaligus (sekali di awal)
  python weathercloud_sync.py --clean file.csv  # rapikan CSV hasil download manual

Login dibaca dari environment variable WC_USER dan WC_PASS (jangan tulis password di file ini).
"""
import argparse
import io
import os
import re
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import requests

BASE = "https://app.weathercloud.net"
TZ = ZoneInfo("Asia/Jakarta")
OUT = Path(__file__).parent / "data"

# ID device dari halaman Database Weathercloud
STATIONS = {
    "ITS_Kampus_Sukolilo": "2058506535",
    "Keputih": "4635331011",
}


# ---------------------------------------------------------------- download
def login(user: str, password: str) -> requests.Session:
    s = requests.Session()
    s.headers["User-Agent"] = "Mozilla/5.0 (ITS weathercloud sync)"
    s.get(f"{BASE}/signin", timeout=60)
    r = s.post(
        f"{BASE}/signin",
        data={
            "LoginForm[entity]": user,
            "LoginForm[password]": password,
            "LoginForm[rememberMe]": "0",
        },
        allow_redirects=False,
        timeout=60,
    )
    if r.status_code != 302:
        sys.exit("Login gagal: cek WC_USER / WC_PASS.")
    return s


def csrf_token(s: requests.Session) -> str:
    html = s.get(f"{BASE}/database", timeout=60).text
    m = re.search(r'WEATHERCLOUD_CSRF_TOKEN:"([^"]+)"', html)
    if not m:
        sys.exit("Token halaman Database tidak ditemukan (belum login, atau tampilan Weathercloud berubah).")
    return m.group(1)


def download_raw(s, token, device, start: datetime, end: datetime) -> bytes:
    fmt = "%Y-%m-%dT%H:%M:%S"
    r = s.post(
        f"{BASE}/data/csv/",
        data={"device": device, "start": start.strftime(fmt), "end": end.strftime(fmt),
              "WEATHERCLOUD_CSRF_TOKEN": token},
        headers={"X-Requested-With": "XMLHttpRequest"},
        timeout=120,
    )
    r.raise_for_status()
    info = r.json()
    if info.get("status") != "success":
        raise RuntimeError(f"Export ditolak: {info}")
    f = s.get(f"{BASE}/data/download/file/{info['filename']}", timeout=120)
    f.raise_for_status()
    return f.content


# ---------------------------------------------------------------- cleaning
def clean(raw: bytes) -> pd.DataFrame:
    """CSV Weathercloud (UTF-16, ';', angka '1,011.8') -> DataFrame rapi."""
    text = raw.decode("utf-16-le" if raw[1:2] == b"\x00" else "utf-8", errors="replace").lstrip("﻿")
    df = pd.read_csv(io.StringIO(text), sep=";", index_col=False, thousands=",", decimal=".")
    df = df.loc[:, ~df.columns.str.startswith("Unnamed")]
    date_col = df.columns[0]
    df[date_col] = pd.to_datetime(df[date_col], format="%d/%m/%Y %H:%M:%S", errors="coerce")
    df = df.rename(columns={date_col: "Waktu (WIB)"}).dropna(subset=["Waktu (WIB)"])
    return df


def merge_save(new: pd.DataFrame, folder: Path, name: str, month: str):
    folder.mkdir(parents=True, exist_ok=True)
    csv_path = folder / f"{name}_{month}.csv"
    df = new
    if csv_path.exists():  # gabung dengan data lama supaya tidak ada yang hilang
        old = pd.read_csv(csv_path, parse_dates=["Waktu (WIB)"])
        df = pd.concat([old, new])
    df = (df.drop_duplicates("Waktu (WIB)", keep="last")
            .sort_values("Waktu (WIB)")
            .dropna(axis=1, how="all"))          # buang kolom sensor yang tidak ada
    df.to_csv(csv_path, index=False, date_format="%Y-%m-%d %H:%M:%S")
    df.to_excel(folder / f"{name}_{month}.xlsx", index=False)
    return len(df)


def rebuild_all(folder: Path, name: str):
    parts = sorted(folder.glob(f"{name}_????-??.csv"))
    if parts:
        df = pd.concat([pd.read_csv(p) for p in parts]).drop_duplicates("Waktu (WIB)", keep="last")
        df.sort_values("Waktu (WIB)").to_csv(folder / f"{name}_semua.csv", index=False)


# ---------------------------------------------------------------- main
def months_to_fetch(backfill: int):
    now = datetime.now(TZ).replace(tzinfo=None)
    first = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    n = max(backfill, 2 if now.day <= 3 else 1)  # awal bulan: lengkapi juga bulan lalu
    out = []
    for _ in range(n):
        nxt = (first + timedelta(days=32)).replace(day=1)
        end = min(nxt - timedelta(seconds=1), now)
        out.append((first, end))
        first = (first - timedelta(days=1)).replace(day=1)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backfill", type=int, default=0, help="jumlah bulan ke belakang yang diambil")
    ap.add_argument("--clean", nargs="+", metavar="CSV", help="rapikan file CSV manual saja")
    args = ap.parse_args()

    if args.clean:
        for p in map(Path, args.clean):
            df = clean(p.read_bytes()).dropna(axis=1, how="all")
            out = p.with_name(p.stem + "_rapi.xlsx")
            df.to_excel(out, index=False)
            print(f"{p.name} -> {out.name} ({len(df)} baris)")
        return

    user, pw = os.environ.get("WC_USER"), os.environ.get("WC_PASS")
    if not user or not pw:
        sys.exit("Isi environment variable WC_USER dan WC_PASS dulu.")
    s = login(user, pw)
    token = csrf_token(s)

    for name, device in STATIONS.items():
        folder = OUT / name
        for start, end in months_to_fetch(args.backfill):
            month = start.strftime("%Y-%m")
            try:
                df = clean(download_raw(s, token, device, start, end))
            except Exception as e:
                print(f"[GAGAL] {name} {month}: {e}")
                continue
            if df.drop(columns="Waktu (WIB)").notna().any(axis=None):
                n = merge_save(df, folder, name, month)
                print(f"[OK] {name} {month}: {n} baris")
            else:
                print(f"[KOSONG] {name} {month}: tidak ada data")
            time.sleep(2)  # jangan membebani server
        rebuild_all(folder, name)


if __name__ == "__main__":
    main()
