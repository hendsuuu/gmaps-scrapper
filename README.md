# Google Maps Leads Scraper

> Production-ready Apify Actor that scrapes business leads from **Google Maps** and exports to **CSV + JSON**. Supports proxy rotation via `proxies.txt`.

---

## Table of Contents

1. [Features](#features)
2. [Output Columns](#output-columns)
3. [Quick Start – Local](#quick-start--local)
4. [Quick Start – Apify Cloud](#quick-start--apify-cloud)
5. [Input Parameters](#input-parameters)
6. [Project Structure](#project-structure)
7. [Development Guide](#development-guide)
8. [Monetisation Tips](#monetisation-tips)
9. [FAQ & Troubleshooting](#faq--troubleshooting)

---

## Features

| Feature                          | Detail                                                                      |
| -------------------------------- | --------------------------------------------------------------------------- |
| **Multi-query × Multi-location** | Run any number of keyword + location combinations in one run                |
| **Rich data extraction**         | 19+ fields per business (see table below)                                   |
| **proxies.txt rotation**         | Drop proxy URLs into `proxies.txt` and they rotate automatically            |
| **CSV + JSON export**            | Always saved locally and to Apify Key-Value Store                           |
| **Apify Dataset**                | Every record pushed to Apify Dataset (downloadable as CSV/JSON/XLSX via UI) |
| **Rate-limit friendly**          | Controlled scrolling, human-like delays, random proxy selection             |
| **Docker-ready**                 | Ships with a multi-stage Dockerfile                                         |
| **Local CLI mode**               | Test without Apify infrastructure                                           |

---

## Output Columns

| Column               | Description                         |
| -------------------- | ----------------------------------- |
| `place_id`           | Unique Google Maps place identifier |
| `name`               | Business name                       |
| `category`           | Business category / type            |
| `phone`              | Contact phone number                |
| `website`            | Official website URL                |
| `rating`             | Star rating (0–5)                   |
| `review_count`       | Number of Google reviews            |
| `address`            | Full formatted address              |
| `city`               | Parsed city name                    |
| `state`              | State / province                    |
| `postal_code`        | ZIP / postal code                   |
| `country`            | Country name                        |
| `latitude`           | GPS latitude                        |
| `longitude`          | GPS longitude                       |
| `opening_hours`      | Operating hours summary             |
| `price_range`        | Price indicator ($ – $$$$)          |
| `permanently_closed` | True / False                        |
| `plus_code`          | Google Plus Code                    |
| `google_maps_url`    | Direct Google Maps URL              |
| `search_query`       | The keyword used for this result    |
| `search_location`    | The location used for this result   |

---

## Quick Start – Local

### 1. Prerequisites

```bash
# Python 3.11+
python --version

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers (first time only)
playwright install chromium
```

### 2. (Optional) Add proxies

Copy the example file and fill in your proxies:

```bash
copy proxies.txt.example proxies.txt
```

Edit `proxies.txt` – one proxy per line:

```
# proxies.txt
http://user1:pass1@proxy1.example.com:8080
http://user2:pass2@proxy2.example.com:3128
203.0.113.10:8888
```

The scraper randomly picks one proxy per run. Leave the file empty (or omit it) to run without proxy.

### 3. Run a scrape

```bash
python run_local.py \
  --query "restaurant" \
  --location "Bali, Indonesia" \
  --max 50
```

This always saves **two files** automatically:

- `leads.csv` – UTF-8 CSV (opens directly in Excel)
- `leads.json` – JSON array

**More examples:**

```bash
# Hotels in Tokyo, 30 results
python run_local.py -q "hotel" -l "Tokyo, Japan" -m 30

# Travel agents in Singapore with custom proxies file
python run_local.py -q "travel agent" -l "Singapore" -m 80 --proxies my_proxies.txt

# Coffee shops in London, visible browser (debug mode)
python run_local.py -q "coffee shop" -l "London, UK" -m 20 --visible

# Custom output filename
python run_local.py -q "hospital" -l "Jakarta, Indonesia" -m 100 -o jakarta_hospitals.csv
```

### 4. CLI reference

```
usage: run_local.py [-h]
                    --query QUERY
                    --location LOCATION
                    [--max MAX]
                    [--output OUTPUT]
                    [--proxies PROXIES]
                    [--headless | --visible]

Options:
  -q, --query       Search keyword (e.g. "restaurant")
  -l, --location    Location (e.g. "Bali, Indonesia")
  -m, --max         Max results [default: 50]
  -o, --output      Output base path [default: leads.csv]
                    Both leads.csv and leads.json are always saved.
  -p, --proxies     Path to proxies.txt [default: proxies.txt]
  --visible         Show the browser window (debug mode)
```

---

## Quick Start – Apify Cloud

### 1. Push to Apify

```bash
# Install Apify CLI
npm install -g apify-cli

# Login
apify login

# Deploy the actor
apify push
```

### 2. Configure input on Apify Console

Go to your Actor → **Input** tab and fill in:

```json
{
  "queries": ["restaurant", "cafe", "hotel"],
  "locations": ["Bali, Indonesia", "Lombok, Indonesia"],
  "maxResultsPerQuery": 100,
  "language": "en",
  "proxyList": [
    "http://user1:pass1@proxy1.example.com:8080",
    "http://user2:pass2@proxy2.example.com:3128"
  ]
}
```

> **Tip:** Leave `proxyList` empty `[]` to run without proxy, or upload a `proxies.txt` file as an actor asset.

### 3. Run & Download

- Click **Start** to run the actor.
- After completion download results from the **Key-Value Store** tab:
  - `leads.csv` – ready to open in Excel / Google Sheets
  - `leads.json` – full JSON with all fields
- Or download any format from the **Dataset** tab.

---

## Input Parameters

| Parameter            | Type       | Required | Default | Description                                                    |
| -------------------- | ---------- | -------- | ------- | -------------------------------------------------------------- |
| `queries`            | `string[]` | ✅       | –       | Search keywords (e.g. `["restaurant", "hotel"]`)               |
| `locations`          | `string[]` | ✅       | –       | Locations to search in                                         |
| `maxResultsPerQuery` | `integer`  | ❌       | `100`   | Max leads per query×location pair                              |
| `language`           | `string`   | ❌       | `"en"`  | Browser locale (`en`, `id`, `de`, …)                           |
| `proxyList`          | `string[]` | ❌       | `[]`    | Proxy URLs for rotation (format: `http://user:pass@host:port`) |
| `headless`           | `boolean`  | ❌       | `true`  | Headless Chromium                                              |

---

## Project Structure

```
leads_scrapper/
├── .actor/
│   ├── actor.json          # Apify actor manifest
│   └── input_schema.json   # Input schema (rendered as UI on Apify)
├── src/
│   ├── __init__.py
│   ├── main.py             # Apify Actor entry point
│   ├── scraper.py          ← Core Playwright scraping engine + load_proxies()
│   └── utils.py            ← Logging, text helpers
├── run_local.py            ← CLI runner for local testing
├── proxies.txt             ← Your proxies (gitignored)
├── proxies.txt.example     ← Proxy file template
├── requirements.txt
├── Dockerfile
├── .env.example
├── .gitignore
└── README.md
```

---

## Development Guide

### Install dev dependencies

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
playwright install chromium
```

### Run tests locally

```bash
python run_local.py -q "coffee shop" -l "Yogyakarta, Indonesia" -m 10 --visible
```

### Environment variables (`.env`)

Copy `.env.example` → `.env`. At the moment only `PROXIES_FILE` is supported.

### Proxy setup

1. Copy `proxies.txt.example` → `proxies.txt`
2. Add one proxy per line
3. Run normally – the scraper picks a random proxy per run
4. For Apify Cloud: pass proxy URLs in the `proxyList` input field

### Debugging tips

| Problem                | Solution                                                              |
| ---------------------- | --------------------------------------------------------------------- |
| No results returned    | Try `--visible` to watch the browser; check if consent popup appeared |
| Rate-limited / CAPTCHA | Add proxies to `proxies.txt`                                          |
| Missing phone/website  | Some businesses don't list them on Maps                               |
| Address parsing wrong  | The raw `address` field is always populated correctly                 |

---

## Monetisation Tips

This actor is designed to be published on the **Apify Store**.

### Pricing models

| Model                    | Recommendation                                       |
| ------------------------ | ---------------------------------------------------- |
| **Pay-per-result**       | Charge per lead scraped (e.g. $0.005–$0.01 per lead) |
| **Monthly subscription** | Fixed quota (e.g. 10,000 leads/month)                |
| **Free trial**           | 50 free leads, then paid                             |

### Recommended actor.json categories

```json
"categories": ["LEAD_GENERATION", "BUSINESS", "MARKETING"]
```

### SEO title & description tips

- Title: `Google Maps Business Leads Scraper`
- Keywords: `google maps scraper`, `leads scraper`, `business directory`, `contact scraper`, `google maps extractor`

---

## FAQ & Troubleshooting

**Q: How many leads can I scrape per run?**  
Google Maps typically shows up to ~120 results per search. Use multiple queries or narrow locations to get more targeted leads.

**Q: Where do I find the exported files on Apify?**  
Go to your run → **Key-Value Store** tab. Download `leads.csv` or `leads.json` directly.

**Q: How does proxy rotation work?**  
The scraper reads all lines from `proxies.txt` (or the `proxyList` input), then picks one at random for each browser session. Each query×location pair spawns a new browser with a fresh random proxy.

**Q: What proxy format is supported?**  
HTTP proxies: `http://user:pass@host:port` or `http://host:port` or bare `host:port`. SOCKS5 is not currently supported.

**Q: Is this compliant with Google's Terms of Service?**  
Web scraping public data is a legal grey area. Review Google's ToS and your local laws. This actor scrapes only publicly visible information. For commercial use, consider using the [Google Places API](https://developers.google.com/maps/documentation/places/web-service/overview).

**Q: The actor times out on Apify.**  
Increase the actor timeout in the Settings tab, or reduce `maxResultsPerQuery`. Each listing takes ~3–5 seconds to scrape.

**Q: Can I scrape multiple keywords at once?**  
Yes! Pass multiple values in the `queries` array: `["restaurant", "cafe", "bakery"]`.

---

## License

MIT – free to use, modify, and publish on Apify Store.
