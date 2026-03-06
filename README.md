# 🗺️ Google Maps Leads Scraper

**Extract business leads from Google Maps — phone, website, address, rating, reviews, and more — exported instantly to CSV & JSON.**

Perfect for lead generation, market research, competitor analysis, and building targeted business databases.

---

## 🚀 What It Does

This Actor scrapes publicly available business information from Google Maps based on your search keywords and locations. Each run produces a clean, structured dataset ready to import into Excel, Google Sheets, CRM tools, or any data pipeline.

---

## ✨ Features

| Feature | Detail |
|---|---|
| **Multi-query × Multi-location** | Run any number of keyword + location combinations in one run |
| **Rich data extraction** | 19+ fields per business |
| **Proxy rotation** | Supply a list of proxy URLs — rotated automatically for reliability |
| **CSV + JSON export** | Both formats always saved to Key-Value Store for direct download |
| **Apify Dataset** | Every record pushed to Dataset (exportable as CSV / JSON / XLSX / XML) |
| **Reliable connection** | Proxy used only for search page; detail pages fetched via direct connection |
| **Production-ready** | Battle-tested Playwright engine, graceful error handling, skip-and-continue |

---

## 📋 Output Fields

| Field | Description |
|---|---|
| `place_id` | Unique Google Maps place identifier |
| `name` | Business name |
| `category` | Business category / type |
| `phone` | Contact phone number |
| `website` | Official website URL |
| `rating` | Star rating (0–5) |
| `review_count` | Total number of Google reviews |
| `address` | Full formatted address |
| `city` | Parsed city name |
| `state` | State / province |
| `postal_code` | ZIP / postal code |
| `country` | Country name |
| `latitude` | GPS latitude |
| `longitude` | GPS longitude |
| `opening_hours` | Operating hours summary |
| `price_range` | Price indicator ($ – $$$$) |
| `permanently_closed` | Whether the business is permanently closed |
| `plus_code` | Google Plus Code |
| `google_maps_url` | Direct link to the Google Maps listing |
| `search_query` | The keyword used for this result |
| `search_location` | The location used for this result |

---

## ⚙️ Input Parameters

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `queries` | `string[]` | ✅ | – | Search keywords, e.g. `["restaurant", "hotel", "travel agent"]` |
| `locations` | `string[]` | ✅ | – | Locations to search, e.g. `["Bali, Indonesia", "New York, USA"]` |
| `maxResultsPerQuery` | `integer` | ❌ | `100` | Max leads per keyword × location pair (max 1000) |
| `language` | `string` | ❌ | `en` | Browser locale — affects language of returned data |
| `proxyList` | `string[]` | ❌ | `[]` | Proxy URLs for rotation (`http://user:pass@host:port`). Leave empty to run direct. |
| `headless` | `boolean` | ❌ | `true` | Run browser headless (always `true` on Apify Cloud) |

---

## 📥 Example Input

```json
{
  "queries": ["restaurant", "cafe", "hotel"],
  "locations": ["Bali, Indonesia", "Lombok, Indonesia"],
  "maxResultsPerQuery": 100,
  "language": "en",
  "proxyList": []
}
```

---

## 📤 Downloading Results

After the run completes:

1. **Key-Value Store tab** → download `leads.csv` (open directly in Excel / Google Sheets) or `leads.json`
2. **Dataset tab** → export in CSV, JSON, XLSX, XML, or RSS format
3. **API** → integrate directly into your pipeline via the Apify API

---

## 💻 Local Usage (CLI)

```bash
# Install dependencies
pip install -r requirements.txt
playwright install chromium

# Run a scrape
python run_local.py --query "restaurant" --location "Bali, Indonesia" --max 50

# With proxy file
python run_local.py -q "hotel" -l "Tokyo, Japan" -m 30 --proxies proxies.txt

# Custom output name
python run_local.py -q "clinic" -l "Jakarta, Indonesia" -m 100 -o jakarta_clinics

# Visible browser (debug)
python run_local.py -q "coffee shop" -l "Singapore" -m 20 --visible
```

Output files are always auto-named: `restaurant_bali-indonesia_20260306_083000.csv` + `.json`

### CLI Options

| Flag | Short | Default | Description |
|---|---|---|---|
| `--query` | `-q` | required | Search keyword |
| `--location` | `-l` | required | Location to search |
| `--max` | `-m` | `50` | Max results |
| `--output` | `-o` | auto-generated | Base filename (no extension needed) |
| `--proxies` | `-p` | `proxies.txt` | Path to proxy list file |
| `--visible` | | headless | Show browser window |

---

## 🔧 Proxy Setup

Create a `proxies.txt` file — one proxy per line:

```
# Blank lines and # comments are ignored
http://user1:pass1@proxy1.example.com:8080
http://user2:pass2@proxy2.example.com:3128
203.0.113.10:8888
```

The scraper:
- Randomly samples up to **20 proxies** for the initial search page connection
- Uses the **first working proxy** to collect listing URLs
- Switches to **direct connection** for scraping each listing detail (faster, more stable)
- **Falls back to direct connection** if all proxies fail

---

## 🏗️ Project Structure

```
leads_scrapper/
├── .actor/
│   ├── actor.json           Apify actor manifest
│   └── input_schema.json    Input form schema for Apify Console
├── src/
│   ├── main.py              Apify Actor entry point
│   ├── scraper.py           Playwright scraping engine
│   └── utils.py             Logging & text helpers
├── run_local.py             CLI runner for local testing
├── proxies.txt.example      Proxy file template
├── requirements.txt
├── Dockerfile
└── README.md
```

---

## ❓ FAQ

**How many results can I get per search?**
Google Maps shows up to ~120 listings per search query. For more leads, use multiple keywords or split your location into smaller areas (e.g. by district instead of whole city).

**Why are some fields empty?**
Not every business fills in all their Google Maps details. Phone, website, and opening hours are only visible if the business owner has added them.

**Why does it take a while to start?**
When proxies are configured, the scraper tests them one by one (up to 20) until it finds a working one. This can take 30–90 seconds before the first result appears.

**Can I run multiple keywords at once?**
Yes — pass them as an array: `["restaurant", "cafe", "warung", "bakery"]`. Each keyword is combined with each location.

**The run timed out on Apify.**
Increase the actor timeout in **Settings → Timeout**. Each listing takes ~3–8 seconds. For 100 results, allow at least 15 minutes.

**Results are in the wrong language.**
Set the `language` input to match your target region, e.g. `"id"` for Indonesian, `"ja"` for Japanese.

---

## 🆘 Support & Contact

Encountered a bug, unexpected output, or need a custom feature?

- **GitHub Issues:** [github.com/hendsuuu/gmaps-scrapper/issues](https://github.com/hendsuuu/gmaps-scrapper/issues)
  Open a ticket with the error log and your input configuration — I'll respond within 24–48 hours.
- **Apify Community:** [community.apify.com](https://community.apify.com)
  Post in the community forum for general Apify-related questions.

When reporting an issue, please include:
1. Your input JSON (`queries`, `locations`, `maxResultsPerQuery`)
2. The full error message from the Actor log
3. The Actor run ID (visible in the Apify Console URL)

---

## ⚠️ Disclaimer

This Actor scrapes **publicly available data** from Google Maps. Always ensure your use complies with Google's [Terms of Service](https://policies.google.com/terms) and applicable local laws. For high-volume commercial use, consider the official [Google Places API](https://developers.google.com/maps/documentation/places/web-service/overview).

---

## 📄 License

MIT — free to use, fork, and build upon.
