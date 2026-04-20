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
