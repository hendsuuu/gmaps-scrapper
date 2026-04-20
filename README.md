# Backend Scraper Service

Backend ini berisi:

- engine scraping Google Maps berbasis Playwright
- FastAPI service untuk job scraping dengan progress tracking
- penyimpanan output otomatis ke `data/json` dan `data/excel`

## Jalankan API

```bash
pip install -r requirements.txt
playwright install chromium
uvicorn src.api:app --reload --host 0.0.0.0 --port 8000
```

## Jalankan scraper CLI

```bash
python run_local.py --query "clinic" --location "Semarang, Indonesia" --max 20
```

## Endpoint

- `GET /api/health`
- `POST /api/scrape/jobs`
- `GET /api/scrape/jobs/{job_id}`

## Format request create job

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
