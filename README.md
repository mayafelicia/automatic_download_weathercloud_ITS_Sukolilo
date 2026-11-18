# Data Stasiun Cuaca ITS (Weathercloud) – Download Otomatis

Repository ini mengambil data dari Weathercloud **setiap hari pukul 00:20 WIB** untuk:

| Stasiun | Device ID |
|---|---|
| ITS Kampus Sukolilo | 2058506535 |
| Keputih | 4635331011 |

Data disimpan rapi di folder `data/`:

```
data/
├── ITS_Kampus_Sukolilo/
│   ├── ITS_Kampus_Sukolilo_2026-11.csv    ← CSV standar (koma, desimal titik, UTF-8)
│   ├── ITS_Kampus_Sukolilo_2026-11.xlsx   ← buka ini kalau pakai Excel
│   └── ITS_Kampus_Sukolilo_semua.csv      ← gabungan semua bulan
└── Keputih/
    └── ...
```

- Interval 10 menit, waktu dalam WIB (kolom `Waktu (WIB)`, format `YYYY-MM-DD HH:MM:SS`).
- Baris yang angkanya kosong = stasiun tidak mengirim data pada jam itu (sengaja tidak dihapus supaya deret waktunya tetap utuh).
- Kolom sensor yang tidak dimiliki stasiun (PM2.5, CO, NO2, dst.) dibuang.

> **Penting:** akun Weathercloud gratis hanya menyimpan data **12 bulan terakhir**. Repository ini menjadi arsip permanen, jadi data lama tidak hilang.

---

## A. Untuk pengguna data (yang hanya ingin download)

1. **Sekali ambil:** buka folder `data/` → pilih stasiun → klik file → tombol **Download** (ikon ⬇).
2. **Semua sekaligus:** tombol hijau **Code → Download ZIP**.
3. **Selalu terbaru di Excel (tanpa download ulang):**
   Excel → **Data → From Web** → tempel alamat *raw* file, contoh
   `https://raw.githubusercontent.com/<akun>/<repo>/main/data/Keputih/Keputih_semua.csv`
   → di jendela Power Query pilih **File Origin: 65001 UTF-8**, **Delimiter: Comma**, lalu
   *Transform → Data Type → Using Locale → English (United States)* untuk kolom angka.
   Setelah itu cukup klik **Data → Refresh All** kapan saja.
4. **Python:**
   ```python
   import pandas as pd
   url = "https://raw.githubusercontent.com/<akun>/<repo>/main/data/Keputih/Keputih_semua.csv"
   df = pd.read_csv(url, parse_dates=["Waktu (WIB)"])
   ```

(Cara 3 dan 4 langsung berjalan kalau repository **Public**. Kalau **Private**, pengguna harus di-invite sebagai *collaborator* dan download lewat cara 1/2.)

---

## B. Untuk admin (setup sekali saja)

1. Buat akun di github.com → **New repository** (misal `data-cuaca-its`), pilih Public atau Private.
2. Upload semua file proyek ini (termasuk folder `.github/workflows/`) — **Add file → Upload files**.
3. Simpan login Weathercloud sebagai rahasia:
   **Settings → Secrets and variables → Actions → New repository secret**
   - `WC_USER` = email/username Weathercloud
   - `WC_PASS` = password Weathercloud
   (Password tersimpan terenkripsi, tidak terlihat oleh siapa pun termasuk collaborator.)
4. Ambil data lama sekali: tab **Actions → Download data Weathercloud → Run workflow** → isi `backfill` = `12` → Run.
5. Selesai. Mulai besok workflow berjalan sendiri tiap hari; cek tab **Actions** sesekali (centang hijau = sukses).

**Menambah stasiun:** edit `STATIONS` di `weathercloud_sync.py` (ID ada di menu Database Weathercloud, mis. `ITS Kampus (OLD)` = 6865264288).

---

## C. Alternatif tanpa GitHub (komputer lab + Google Drive)

1. Install Python, lalu `pip install -r requirements.txt`.
2. Taruh folder proyek ini di dalam folder Google Drive/OneDrive yang dibagikan ke tim.
3. Buat file `jalankan.bat`:
   ```bat
   @echo off
   set WC_USER=email@contoh.com
   set WC_PASS=passwordanda
   cd /d "%~dp0"
   python weathercloud_sync.py >> log.txt 2>&1
   ```
4. **Task Scheduler → Create Basic Task → Daily 00:20 → Start a program → `jalankan.bat`**.
   Komputer harus menyala pada jam itu (atau centang *Run task as soon as possible after a scheduled start is missed*).
   Jangan bagikan `jalankan.bat` karena berisi password.

---

## Merapikan CSV hasil download manual

```
python weathercloud_sync.py --clean "Weathercloud Keputih 2025-12.csv"
```
Menghasilkan `..._rapi.xlsx` yang langsung benar dibuka di Excel.
