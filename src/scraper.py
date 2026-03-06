"""
Core Google Maps scraper engine.
Uses Playwright for browser automation to extract business data from Google Maps.
"""

import asyncio
import random
import re
import logging
from typing import Optional
from dataclasses import dataclass, asdict
from urllib.parse import quote_plus

from playwright.async_api import async_playwright, Browser, Page, TimeoutError as PlaywrightTimeoutError

logger = logging.getLogger(__name__)


@dataclass
class BusinessLead:
    place_id: str = ""
    name: str = ""
    phone: str = ""
    email: str = ""
    website: str = ""
    rating: Optional[float] = None
    review_count: Optional[int] = None
    address: str = ""
    city: str = ""
    postal_code: str = ""
    country: str = ""
    state: str = ""
    category: str = ""
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    google_maps_url: str = ""
    permanently_closed: bool = False
    plus_code: str = ""
    opening_hours: str = ""
    price_range: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def load_proxies(filepath: str) -> list[str]:
    """Read proxies from a text file – one proxy URL per line.
    Blank lines and lines starting with # are ignored.
    Accepted formats:
        http://user:pass@host:port
        http://host:port
        host:port  (http:// prepended automatically)
    """
    proxies: list[str] = []
    try:
        with open(filepath, "r", encoding="utf-8") as fh:
            for raw in fh:
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                if not line.startswith("http"):
                    line = f"http://{line}"
                proxies.append(line)
        logger.info("Loaded %d proxies from %s", len(proxies), filepath)
    except FileNotFoundError:
        logger.warning(
            "proxies.txt not found at %s – running without proxy", filepath)
    return proxies


class GoogleMapsScraper:
    BASE_URL = "https://www.google.com/maps/search/{query}+{location}"

    def __init__(
        self,
        max_results: int = 100,
        headless: bool = True,
        language: str = "en",
        proxy_list: Optional[list[str]] = None,
    ):
        self.max_results = max_results
        self.headless = headless
        self.language = language
        self.proxy_list: list[str] = proxy_list or []
        self._browser: Optional[Browser] = None

    # ------------------------------------------------------------------
    # Browser lifecycle
    # ------------------------------------------------------------------

    async def _get_browser(self, playwright, proxy: Optional[dict] = None):
        launch_kwargs = {
            "headless": self.headless,
            "args": [
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
                "--ignore-certificate-errors",
                "--ignore-certificate-errors-spki-list",
                "--disable-web-security",
                f"--lang={self.language}",
            ],
        }
        if proxy:
            launch_kwargs["proxy"] = proxy
        return await playwright.chromium.launch(**launch_kwargs)

    async def _new_page(self, browser: Browser) -> Page:
        context = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            locale=self.language,
            ignore_https_errors=True,
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
        )
        page = await context.new_page()
        # Block unnecessary resources to speed up scraping
        await page.route(
            "**/*.{png,jpg,jpeg,gif,webp,svg,woff,woff2,ttf,eot}",
            lambda route: route.abort(),
        )
        return page

    # ------------------------------------------------------------------
    # Main entry
    # ------------------------------------------------------------------

    # Maximum number of proxies to trial before giving up and using direct connection
    MAX_PROXY_ATTEMPTS = 20
    # Timeout (ms) used only for the initial connectivity test
    PROBE_TIMEOUT = 18_000

    async def scrape(self, query: str, location: str) -> list[BusinessLead]:
        """Run a full scrape for *query* in *location*.

        Connection strategy:
        Phase 1 – Search page (proxy preferred for anonymity):
          Try up to MAX_PROXY_ATTEMPTS random proxies with a short probe timeout.
          Falls back to direct connection if all proxies fail.

        Phase 2 – Listing detail pages (always direct connection):
          Proxies are unreliable for sustained page loads, so detail pages are
          always fetched via a separate direct browser. Timeouts are shorter;
          failed listings are skipped and logged instead of aborting the run.
        """
        results: list[BusinessLead] = []
        search_url = self.BASE_URL.format(
            query=quote_plus(query),
            location=quote_plus(location),
        )
        logger.info("Starting scrape: query=%r location=%r", query, location)

        # ── Phase 1: collect listing URLs via proxy (or direct) ───────────────
        listing_urls = await self._fetch_listing_urls(search_url)
        if not listing_urls:
            logger.warning("No listings found – returning empty result")
            return []

        logger.info(
            "Found %d listings – scraping details via direct connection", len(listing_urls))

        # ── Phase 2: scrape each listing detail via direct connection ─────────
        async with async_playwright() as playwright:
            direct_browser = await self._get_browser(playwright, proxy=None)
            try:
                for idx, url in enumerate(listing_urls[: self.max_results]):
                    logger.debug("Detail %d/%d: %s", idx +
                                 1, len(listing_urls), url)
                    lead = await self._scrape_listing(direct_browser, url)
                    if lead:
                        results.append(lead)
                        logger.info(
                            "  [%d/%d] ✓ %s",
                            idx + 1, min(len(listing_urls),
                                         self.max_results), lead.name,
                        )
                    else:
                        logger.info("  [%d/%d] – skipped (no data)", idx + 1,
                                    min(len(listing_urls), self.max_results))
                    await asyncio.sleep(0.4)
            finally:
                await direct_browser.close()

        logger.info("Scrape complete – %d/%d results collected",
                    len(results), min(len(listing_urls), self.max_results))
        return results

    async def _fetch_listing_urls(self, search_url: str) -> list[str]:
        """
        Phase 1: open the search results page (with proxy fallback) and return
        all listing URLs.  The browser is closed immediately after.
        """
        # Build ordered candidate list: sampled proxies → None (direct)
        proxy_candidates: list[Optional[str]] = []
        if self.proxy_list:
            sample_size = min(len(self.proxy_list), self.MAX_PROXY_ATTEMPTS)
            proxy_candidates = random.sample(self.proxy_list, sample_size)
            logger.info(
                "Phase 1 – testing up to %d proxies for search page",
                sample_size,
            )
        proxy_candidates.append(None)  # direct connection as last resort

        async with async_playwright() as playwright:
            for candidate in proxy_candidates:
                proxy_dict = {"server": candidate} if candidate else None
                label = candidate if candidate else "direct (no proxy)"
                logger.info("  Trying: %s", label)
                tmp_browser = None
                try:
                    tmp_browser = await self._get_browser(playwright, proxy=proxy_dict)
                    tmp_page = await self._new_page(tmp_browser)
                    await tmp_page.goto(
                        search_url,
                        timeout=self.PROBE_TIMEOUT,
                        wait_until="domcontentloaded",
                    )
                    logger.info("  Connected via: %s", label)
                    await self._dismiss_consent(tmp_page)
                    urls = await self._collect_listing_urls(tmp_page)
                    await tmp_browser.close()
                    return urls
                except Exception as exc:
                    err_short = str(exc).split("\n")[0][:120]
                    logger.warning("  Failed (%s): %s", label, err_short)
                    if tmp_browser:
                        try:
                            await tmp_browser.close()
                        except Exception:
                            pass

        logger.error("All connection attempts failed for search page")
        return []

    # ------------------------------------------------------------------
    # Consent / cookie popup
    # ------------------------------------------------------------------

    async def _dismiss_consent(self, page: Page) -> None:
        try:
            btn = page.locator(
                'button[aria-label*="Accept"], button[jsname="higCR"]')
            if await btn.count() > 0:
                await btn.first.click(timeout=5_000)
                await page.wait_for_timeout(1_000)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Collect listing URLs from search results page
    # ------------------------------------------------------------------

    async def _collect_listing_urls(self, page: Page) -> list[str]:
        """Scroll through the results pane and collect all place URLs."""
        urls: list[str] = []
        seen: set[str] = set()

        results_pane_selector = 'div[role="feed"]'
        try:
            await page.wait_for_selector(results_pane_selector, timeout=15_000)
        except PlaywrightTimeoutError:
            logger.warning(
                "Results feed not found – possibly a single result page")
            # Handle single-result redirect
            current_url = page.url
            if "/place/" in current_url:
                return [current_url]
            return []

        previous_count = 0
        stall_count = 0

        while len(urls) < self.max_results and stall_count < 5:
            # Grab all listing anchors currently visible
            cards = await page.locator('a[href*="/maps/place/"]').all()
            for card in cards:
                href = await card.get_attribute("href")
                if href and href not in seen:
                    # Normalise – keep only up to the place reference
                    clean = re.sub(r"&ved=.*", "", href)
                    seen.add(href)
                    urls.append(clean)

            if len(urls) == previous_count:
                stall_count += 1
            else:
                stall_count = 0
            previous_count = len(urls)

            # Scroll down to load more
            feed = page.locator(results_pane_selector)
            await feed.evaluate("el => el.scrollBy(0, el.scrollHeight)")
            await page.wait_for_timeout(1_500)

            # Check for "end of list" signal
            end_marker = page.locator(
                'span:has-text("You\'ve reached the end of the list")')
            if await end_marker.count() > 0:
                break

        return urls[: self.max_results]

    # ------------------------------------------------------------------
    # Scrape individual listing
    # ------------------------------------------------------------------

    async def _scrape_listing(self, browser: Browser, url: str) -> Optional[BusinessLead]:
        page = await self._new_page(browser)
        lead = BusinessLead()
        try:
            await page.goto(url, timeout=30_000, wait_until="domcontentloaded")
            await page.wait_for_timeout(2_000)

            lead.google_maps_url = page.url

            # Extract place_id from URL
            place_id_match = re.search(r"place/[^/]+/([^/?]+)", page.url)
            if place_id_match:
                lead.place_id = place_id_match.group(1)
            # Fallback: look for ChIJ patterns in URL
            if not lead.place_id:
                cij_match = re.search(r"(ChIJ[^&?/]+)", page.url)
                if cij_match:
                    lead.place_id = cij_match.group(1)

            # Name
            try:
                name_el = page.locator(
                    'h1[class*="DUwDvf"], h1.fontHeadlineLarge').first
                lead.name = (await name_el.inner_text(timeout=5_000)).strip()
            except Exception:
                pass

            # Category
            try:
                cat_el = page.locator(
                    'button[jsaction*="category"], span.DkEaL').first
                lead.category = (await cat_el.inner_text(timeout=3_000)).strip()
            except Exception:
                pass

            # Rating
            try:
                rating_el = page.locator(
                    'span[aria-hidden="true"].ceNzKf, div.F7nice span[aria-hidden="true"]').first
                raw_rating = (await rating_el.inner_text(timeout=3_000)).strip()
                lead.rating = float(raw_rating.replace(",", "."))
            except Exception:
                pass

            # Review count
            try:
                review_el = page.locator(
                    'span[aria-label*="review"], button[jsaction*="reviewChart"] span').first
                raw_reviews = (await review_el.inner_text(timeout=3_000)).strip()
                digits = re.sub(r"[^\d]", "", raw_reviews)
                if digits:
                    lead.review_count = int(digits)
            except Exception:
                pass

            # Address + city + postal code parsing
            try:
                addr_btn = page.locator('button[data-item-id="address"]').first
                raw_addr = (await addr_btn.get_attribute("aria-label", timeout=3_000) or "").replace("Address: ", "").strip()
                if not raw_addr:
                    addr_el = page.locator(
                        '[data-item-id="address"] .fontBodyMedium').first
                    raw_addr = (await addr_el.inner_text(timeout=3_000)).strip()
                lead.address = raw_addr
                self._parse_address(lead)
            except Exception:
                pass

            # Phone
            try:
                phone_btn = page.locator(
                    'button[data-item-id*="phone:tel:"]').first
                raw_phone = await phone_btn.get_attribute("aria-label", timeout=3_000)
                if raw_phone:
                    lead.phone = raw_phone.replace("Phone: ", "").strip()
            except Exception:
                pass

            # Website
            try:
                web_btn = page.locator(
                    'a[data-item-id="authority"], a[aria-label*="website"], a[href*="http"][data-tooltip*="website"]').first
                lead.website = (await web_btn.get_attribute("href", timeout=3_000) or "").strip()
            except Exception:
                pass

            # Email – scrape from business website
            if lead.website:
                try:
                    lead.email = await self._scrape_email_from_website(browser, lead.website)
                except Exception as e:
                    logger.debug("Email scrape failed for %s: %s",
                                 lead.website, e)

            # Permanently closed
            try:
                closed_el = page.locator(
                    'span.ZDu9vd span:has-text("Permanently closed")').first
                if await closed_el.count() > 0:
                    lead.permanently_closed = True
            except Exception:
                pass

            # Opening hours
            try:
                hours_btn = page.locator(
                    'div[aria-label*="Hours"], table.eK4R0e').first
                if await hours_btn.count() > 0:
                    lead.opening_hours = (await hours_btn.inner_text(timeout=3_000)).strip().replace("\n", "; ")
            except Exception:
                pass

            # Price range
            try:
                price_el = page.locator(
                    'span.mgr77e span:has-text("$"), span.mgr77e span:has-text("€")').first
                if await price_el.count() > 0:
                    lead.price_range = (await price_el.inner_text(timeout=3_000)).strip()
            except Exception:
                pass

            # Coordinates from URL
            coords_match = re.search(r"@(-?\d+\.?\d*),(-?\d+\.?\d*)", page.url)
            if coords_match:
                lead.latitude = float(coords_match.group(1))
                lead.longitude = float(coords_match.group(2))

            # Plus code
            try:
                plus_el = page.locator(
                    'button[data-item-id="oloc"] .fontBodyMedium').first
                lead.plus_code = (await plus_el.inner_text(timeout=2_000)).strip()
            except Exception:
                pass

        except Exception as exc:
            logger.error("Error scraping %s: %s", url, exc)
        finally:
            await page.context.close()

        # Only return if we got at least a name
        if lead.name:
            return lead
        return None

    # ------------------------------------------------------------------
    # Email scraping from business website
    # ------------------------------------------------------------------

    # Regex for extracting email addresses from HTML/text
    _EMAIL_RE = re.compile(
        r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}",
        re.IGNORECASE,
    )
    # Prefixes to skip – these are almost never real contact emails
    _EMAIL_BLACKLIST = (
        "noreply", "no-reply", "donotreply", "do-not-reply",
        "support@sentry", "mailer", "bounce", "postmaster",
        "@example", "@domain", "@email", "wixpress",
        "@cloudflare", "@squarespace", "@shopify",
    )

    def _clean_emails(self, candidates: list[str]) -> list[str]:
        """Deduplicate and filter out likely non-contact emails."""
        seen: set[str] = set()
        result: list[str] = []
        for em in candidates:
            em = em.lower().strip(".")
            if em in seen:
                continue
            seen.add(em)
            if any(bl in em for bl in self._EMAIL_BLACKLIST):
                continue
            # Skip image/asset file extensions accidentally matched
            if re.search(r"\.(png|jpg|gif|svg|webp|js|css|woff)$", em):
                continue
            result.append(em)
        return result

    async def _scrape_email_from_website(
        self, browser: Browser, website_url: str
    ) -> str:
        """
        Visit a business website and attempt to extract a contact email.
        Strategy:
          1. Load homepage, look for mailto: links first (high confidence)
          2. Scan full page HTML with regex
          3. If nothing found, try /contact and /about pages
        Returns the first clean email found, or "" if none.
        """
        EMAIL_TIMEOUT = 12_000  # ms per page
        CONTACT_SLUGS = ["/contact", "/contact-us",
                         "/about", "/about-us", "/kontakt"]

        async def _extract_from_page(pg: Page) -> list[str]:
            """Return all raw email candidates from the current page."""
            found: list[str] = []
            # 1) Explicit mailto: href attributes (highest confidence)
            try:
                mailto_links = await pg.locator('a[href^="mailto:"]').all()
                for link in mailto_links:
                    href = await link.get_attribute("href") or ""
                    em = href.replace("mailto:", "").split("?")[0].strip()
                    if em:
                        found.append(em)
            except Exception:
                pass
            # 2) Regex scan over full page HTML
            try:
                html = await pg.content()
                found.extend(self._EMAIL_RE.findall(html))
            except Exception:
                pass
            return found

        page = await self._new_page(browser)
        try:
            # ── Homepage ────────────────────────────────────────────────
            try:
                await page.goto(website_url, timeout=EMAIL_TIMEOUT, wait_until="domcontentloaded")
            except Exception as e:
                logger.debug(
                    "Email scraper: could not load %s (%s)", website_url, e)
                return ""

            candidates = await _extract_from_page(page)
            clean = self._clean_emails(candidates)
            if clean:
                return clean[0]

            # ── Try common contact/about sub-pages ───────────────────────
            from urllib.parse import urlparse, urljoin
            base = f"{urlparse(website_url).scheme}://{urlparse(website_url).netloc}"
            for slug in CONTACT_SLUGS:
                try:
                    await page.goto(urljoin(base, slug), timeout=EMAIL_TIMEOUT, wait_until="domcontentloaded")
                    sub_candidates = await _extract_from_page(page)
                    clean = self._clean_emails(sub_candidates)
                    if clean:
                        return clean[0]
                except Exception:
                    continue
        finally:
            await page.context.close()

        return ""

    # ------------------------------------------------------------------
    # Address parsing helpers
    # ------------------------------------------------------------------

    def _parse_address(self, lead: BusinessLead) -> None:
        """Best-effort parsing of postal code and city from raw address."""
        address = lead.address

        # Postal code patterns (US, UK, ID, AU, EU numeric, etc.)
        postal_patterns = [
            r"\b([A-Z]{1,2}\d[A-Z\d]?\s?\d[A-Z]{2})\b",  # UK
            r"\b(\d{5}(?:-\d{4})?)\b",  # US / ID / generic 5-digit
            r"\b([A-Z]\d[A-Z]\s?\d[A-Z]\d)\b",  # CA
        ]
        for pattern in postal_patterns:
            match = re.search(pattern, address, re.IGNORECASE)
            if match:
                lead.postal_code = match.group(1).strip()
                break

        # Try to extract city – usually the last significant component before country
        parts = [p.strip() for p in address.split(",")]
        if len(parts) >= 2:
            # Heuristic: city is second-to-last or third-to-last part before country
            for part in reversed(parts[:-1]):
                # Skip parts that look like postal codes
                if re.match(r"^\d{4,6}$", part) or part == lead.postal_code:
                    continue
                if part:
                    lead.city = part
                    break
        if len(parts) >= 1:
            lead.country = parts[-1].strip()
        if len(parts) >= 3:
            lead.state = parts[-2].strip()
