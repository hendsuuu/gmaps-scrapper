# Backend Scraper Service

Backend ini berisi:

- Engine scraping Google Maps berbasis Playwright
- Flask (WSGI) service untuk job scraping dengan progress tracking
- Penyimpanan output otomatis ke `data/json` dan `data/excel`

## Prasyarat

```bash
pip install -r requirements.txt
playwright install chromium
```

## Jalankan API (development)

```bash
# Opsi 1 — Flask dev server
flask --app src.api run --host 0.0.0.0 --port 5000 --debug

# Opsi 2 — Waitress (production-grade WSGI server)
waitress-serve --host 0.0.0.0 --port 5000 src.api:app
```

> **Catatan:** Backend sebelumnya menggunakan FastAPI + uvicorn (ASGI).
> Sekarang sudah dimigrasi ke **Flask + waitress (WSGI)** agar kompatibel
> dengan hosting cPanel/Passenger.

## Jalankan via Docker

```bash
docker build -t leads-scraper .
docker run -p 5000:5000 leads-scraper
```

## Jalankan scraper CLI (tanpa web)

```bash
python run_local.py --query "clinic" --location "Semarang, Indonesia" --max 20
```

## Endpoint API

| Method | Path                        | Deskripsi                    |
| ------ | --------------------------- | ---------------------------- |
| GET    | `/api/health`               | Health check                 |
| POST   | `/api/scrape/jobs`          | Buat job scraping baru       |
| GET    | `/api/scrape/jobs/<job_id>` | Cek status & progress job    |
| GET    | `/api/history`              | Daftar file hasil scraping   |
| GET    | `/api/history/<filename>`   | Download file hasil scraping |

## Format request buat job

```json
{
  "query": "clinic",
  "location": "Semarang, Indonesia",
  "max_results": 20
}
```

## Output

- `data/json/<query>_<location>_<timestamp>.json`
- `data/excel/<query>_<location>_<timestamp>.csv`

## Deployment (cPanel / Passenger)

Gunakan `passenger_wsgi.py` → `wsgi.py` → `src.api:app`.
Pastikan Passenger dikonfigurasi untuk Python dan arahkan ke direktori `backend/`.

> **Catatan:** Fitur scraping membutuhkan Playwright + Chromium yang hanya bisa
> dijalankan di VPS / Docker / lokal. Di cPanel shared hosting, endpoint API
> (health, history) tetap berjalan — hanya scraping yang tidak akan bisa jalan.

### Langkah setup di cPanel

1. **Setup Python App** di cPanel → pilih versi Python ≥ 3.10
2. Set **Application root** ke folder `backend/`
3. **Application startup file**: `passenger_wsgi.py` (otomatis terdeteksi)
4. **Application Entry point**: `application`
5. Klik **Create** → masuk ke virtual environment via terminal:

```bash
source /home/<user>/virtualenv/<app-path>/bin/activate
cd /home/<user>/<app-path>
pip install -r requirements.txt
```

6. Jika frontend dihost di domain lain, tambahkan env variable:

```bash
FRONTEND_ORIGIN=https://yourdomain.com,https://www.yourdomain.com
```

7. **Restart** app dari cPanel → buka domain → harus muncul `{"message": "API is running"}`

### Debugging 500 Internal Server Error

- Cek **stderr.log** di folder app cPanel (biasanya `~/app-folder/stderr.log`)
- `wsgi.py` sudah di-wrap try/except sehingga error import akan muncul di stderr.log
- Penyebab umum:
  - Dependency belum terinstall (`pip install -r requirements.txt`)
  - Versi Python terlalu rendah (butuh ≥ 3.10 untuk type hints `dict | None`)
  - Virtual environment tidak aktif / salah path
