"""
browser.py — Production-ready Async Playwright Interaction Engine.

Provides:
  • AsyncBrowserManager: Full interaction-first browser context manager
  • Stealth Mode via playwright-stealth
  • Interactive CAPTCHA Handover (audio alert + visible browser pause, looping wait)
  • Site-specific popup/cookie dismissal for all 34 target sites
  • Smart "Load More" clicking with date-awareness
  • Infinite scroll with height-change detection
  • Paginated next-link traversal
"""

import asyncio
import logging
import random
import re
from pathlib import Path

logger = logging.getLogger("energy_scraper.browser")

# Import the expanded UA pool from fetcher (same process)
try:
    from .fetcher import USER_AGENTS as _UA_POOL
except Exception:
    try:
        from fetcher import USER_AGENTS as _UA_POOL
    except Exception:
        _UA_POOL = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0",
        ]

try:
    from playwright.async_api import async_playwright
    from playwright_stealth import Stealth
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    Stealth = None
    logger.warning("Playwright or playwright-stealth not installed — JS rendering unavailable.")

try:
    from .project_paths import BROWSER_STATE_PATH, ensure_runtime_dirs
except ImportError:
    from project_paths import BROWSER_STATE_PATH, ensure_runtime_dirs

if PLAYWRIGHT_AVAILABLE:
    try:
        _STEALTH_ENGINE = Stealth()
    except Exception:
        _STEALTH_ENGINE = None
else:
    _STEALTH_ENGINE = None


async def _apply_stealth(page) -> None:
    if _STEALTH_ENGINE is None:
        return
    await _STEALTH_ENGINE.apply_stealth_async(page)


# Try winsound for audio CAPTCHA alert (Windows only)
try:
    import winsound
    _WINSOUND_AVAILABLE = True
except ImportError:
    _WINSOUND_AVAILABLE = False


def _play_alert():
    """Play a single audio alert when CAPTCHA handover is needed."""
    if _WINSOUND_AVAILABLE:
        # Single distinct high-low alert — simplified to single long beep
        winsound.Beep(900, 1000)
    else:
        print("\a")  # ASCII bell fallback


class AsyncBrowserManager:
    """
    Async context wrapper around a Playwright Chromium browser.
    Interaction-First Architecture: treats every page as dynamic.
    """

    def __init__(self, headless: bool = False):
        self.headless = headless
        self._pw = None
        self._browser = None
        self._context = None
        self.available = False
        self._nf_email = None
        self._nf_password = None

    async def __aenter__(self):
        if not PLAYWRIGHT_AVAILABLE:
            return self
        try:
            self._pw = await async_playwright().start()
            args = [
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-setuid-sandbox",
                "--disable-web-security",
                "--disable-infobars",
                "--disable-extensions",
                "--disable-plugins-discovery",
            ]
            self._browser = await self._pw.chromium.launch(
                headless=self.headless,
                args=args,
            )
            ua = random.choice(_UA_POOL)
            ensure_runtime_dirs()
            storage_state = str(BROWSER_STATE_PATH) if Path(BROWSER_STATE_PATH).exists() else None
            self._context = await self._browser.new_context(
                user_agent=ua,
                viewport={"width": random.choice([1440, 1920, 1366]), "height": random.choice([900, 1080, 768])},
                java_script_enabled=True,
                bypass_csp=True,
                locale="en-US",
                timezone_id="America/New_York",
                storage_state=storage_state,
            )
            # ── Deep Stealth: Override automation fingerprinting ──
            # This hides navigator.webdriver, chrome object mismatch,
            # and plugins/languages arrays that bot detectors inspect.
            await self._context.add_init_script("""
                // Remove the webdriver flag
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                // Spoof chrome runtime with a realistic object
                if (!window.chrome) {
                    window.chrome = {
                        runtime: {},
                        loadTimes: function() {},
                        csi: function() {},
                        app: {}
                    };
                }
                // Fake plugins array (empty = headless giveaway)
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5]
                });
                // Fake languages
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['en-US', 'en']
                });
                // Fix permissions.query for Notification (headless returns different state)
                const originalQuery = window.navigator.permissions.query;
                window.navigator.permissions.query = (parameters) =>
                    parameters.name === 'notifications'
                        ? Promise.resolve({state: Notification.permission})
                        : originalQuery(parameters);
            """)
            # Block heavy analytics/ads
            await self._context.route(
                re.compile(r"(google-analytics|doubleclick|googlesyndication|adservice|hotjar|intercom|zendesk|hubspot|amplitude)"),
                lambda route: route.abort()
            )
            self.available = True
            logger.info(f"Browser launched (headless={self.headless}, UA=...{ua[-40:]}).")
        except Exception as e:
            logger.error(f"Failed to launch browser: {e}")
            self.available = False
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        try:
            self.available = False
            if self._context:
                try:
                    ensure_runtime_dirs()
                    await self._context.storage_state(path=str(BROWSER_STATE_PATH))
                except Exception:
                    pass
                for page in list(self._context.pages):
                    try:
                        await asyncio.wait_for(page.close(), timeout=5)
                    except Exception:
                        pass
                await asyncio.wait_for(self._context.close(), timeout=10)
            if self._browser:
                await asyncio.wait_for(self._browser.close(), timeout=10)
            if self._pw:
                await asyncio.wait_for(self._pw.stop(), timeout=10)
        except Exception:
            pass
        finally:
            self._context = None
            self._browser = None
            self._pw = None
        logger.debug("Browser closed.")

    async def login_newsfilter(self, email: str, password: str, page_obj=None):
        """Login to newsfilter.io for full M&A feed access. Can run on an existing page."""
        if not self.available:
            return
            
        self._nf_email = email
        self._nf_password = password
        
        page = page_obj if page_obj else await self._context.new_page()
        try:
            logger.info("Newsfilter: Navigating to login...")
            if "newsfilter.io/login" not in page.url:
                await page.goto("https://newsfilter.io/login", wait_until="networkidle", timeout=30000)
            await page.wait_for_timeout(2000)
            await page.fill('input[type="email"]', email)
            await page.fill('input[type="password"]', password)
            login_btn = page.locator(
                'form button[type="submit"]:visible, button:has-text("Log In"):visible, '
                'button:has-text("Sign In"):visible, button:has-text("Login"):visible'
            ).first
            await login_btn.click(timeout=10000)
            
            try:
                # Wait for the login redirect to finish so local storage gets hydrated
                await page.wait_for_url(re.compile(r"newsfilter\.io(?!/login)"), timeout=15000)
                await page.wait_for_load_state("networkidle", timeout=10000)
            except Exception:
                await page.wait_for_timeout(5000)
                
            logger.info("Newsfilter: Login submitted and context hydrated.")
            try:
                ensure_runtime_dirs()
                await self._context.storage_state(path=str(BROWSER_STATE_PATH))
            except Exception:
                pass
        except Exception as e:
            logger.warning(f"Newsfilter login failed: {e}")
        finally:
            if not page_obj:
                await page.close()

    async def _newsfilter_modal_login(self, page) -> bool:
        """Handle the Newsfilter in-page login modal if it appears."""
        if not self._nf_email or not self._nf_password:
            return False

        modal_visible = False
        try:
            modal_visible = await page.locator("text=Log In Required").is_visible(timeout=1500)
        except Exception:
            modal_visible = False

        if not modal_visible:
            return False

        try:
            # Some modal versions show "Already have an account? Sign in here."
            sign_in_here = page.locator("text=/sign in here\\.?/i").first
            if await sign_in_here.is_visible(timeout=1500):
                await sign_in_here.click()
        except Exception:
            pass

        try:
            # Fallbacks: "Already have an account?" or generic "Log in/Sign in"
            login_prompt = page.locator("text=/Already have an account\\?/i").first
            if await login_prompt.is_visible(timeout=1500):
                await login_prompt.click()
        except Exception:
            pass

        try:
            login_link = page.locator("text=/Log in|Sign in/i").first
            if await login_link.is_visible(timeout=1500):
                await login_link.click()
        except Exception:
            pass

        try:
            await page.fill('input[type="email"]', self._nf_email, timeout=5000)
            await page.fill('input[type="password"]', self._nf_password, timeout=5000)
            submit_btn = page.locator(
                'form button[type="submit"]:visible, button:has-text("Log In"):visible, '
                'button:has-text("Sign In"):visible, button:has-text("Login"):visible'
            ).first
            await submit_btn.click(timeout=10000)
            try:
                await page.wait_for_selector("text=Log In Required", state="detached", timeout=10000)
            except Exception:
                pass
            return True
        except Exception as e:
            logger.warning(f"Newsfilter modal login failed: {e}")
            return False

    async def fetch_page(
        self,
        url: str,
        wait_seconds: float = 3.0,
        pagination_type: str | None = None,
        load_more_selector: str | None = None,
        next_page_selector: str | None = None,
        max_pages: int = 3,
        site_name: str = "",
    ) -> str:
        """
        Fetch page source using stealth browser.
        Interaction-First: dismisses popups/cookies, handles CAPTCHA, 
        clicks 'Load More', scrolls, and paginates.
        """
        if not self.available:
            return ""

        page = None
        try:
            page = await self._context.new_page()
            await _apply_stealth(page)
            page.set_default_timeout(45_000)

            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
                # After DOM, wait for network to mostly settle (but don't hard-fail)
                try:
                    await page.wait_for_load_state("networkidle", timeout=8_000)
                except Exception:
                    pass
            except Exception as nav_err:
                logger.debug(f"Navigation issue on {url}: {nav_err}. Proceeding with partial load.")

            try:
                await page.wait_for_selector("body", timeout=15000)
            except Exception:
                pass

            # Step 1: Check and resolve CAPTCHA before any other interaction
            await self._wait_for_human(page)

            # Step 1.5: Newsfilter — force login on every visit to retain session
            if "newsfilter" in site_name.lower():
                if self._nf_email and self._nf_password:
                    logger.info(f"Newsfilter: Forcing login refresh for {url}")
                    await self.login_newsfilter(self._nf_email, self._nf_password, page_obj=page)
                    await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
                    # Handle the in-page modal login if it still appears
                    try:
                        await self._newsfilter_modal_login(page)
                    except Exception:
                        pass
                else:
                    if "newsfilter.io/login" in page.url or await page.locator('input[type="email"]').is_visible(timeout=1500):
                        logger.info(f"Newsfilter: Session dropped on {url}. Re-authenticating dynamically...")
                        if self._nf_email and self._nf_password:
                            await self.login_newsfilter(self._nf_email, self._nf_password, page_obj=page)
                            await page.goto(url, wait_until="domcontentloaded", timeout=30_000)

            # Step 2: Dismiss all overlays / cookie banners / newsletter popups
            await page.wait_for_timeout(int(wait_seconds * 500))  # Half wait before popup dismissal
            await self._dismiss_popups(page, site_name)
            await page.wait_for_timeout(int(wait_seconds * 500))  # Remainder

            # Step 3: Handle pagination / load-more / scroll
            all_html = ""
            if pagination_type == "load_more":
                all_html = await self._handle_load_more(page, load_more_selector, max_pages)
            elif pagination_type == "scroll":
                all_html = await self._handle_infinite_scroll(page, max_pages)
            elif pagination_type == "next_link":
                all_html = await self._handle_next_page(page, next_page_selector, max_pages, url)
            else:
                # Defensive timeout on content extraction
                all_html = await asyncio.wait_for(page.content(), timeout=15)

            try:
                await asyncio.wait_for(page.close(), timeout=10)
            except Exception:
                pass
            return all_html

        except Exception as exc:
            logger.error(f"Browser error on {url}: {exc}")
            try:
                await asyncio.wait_for(page.close(), timeout=5)
            except Exception:
                pass
            return ""

    # ─────────────────────────────────────────────────────────────
    # CAPTCHA & Human Handover
    # ─────────────────────────────────────────────────────────────

    async def _wait_for_human(self, page):
        """
        Detect CAPTCHA/bot challenges.
        Headed mode: plays audio alert + loops until solved (max 2 min).
        Headless mode: logs warning and waits MAX 5s then moves on.
        """
        captcha_selectors = [
            "#challenge-running",
            "#challenge-stage",
            "div.cf-browser-verification",
            ".ray_id",
            "iframe[src*='challenges.cloudflare']",
            "iframe[src*='turnstile']",
            "iframe[title*='reCAPTCHA']",
            "#datadome-captcha",
            "[id*='px-captcha']",
            "h2:has-text('Verify you are human')",
            "h2:has-text('Just a moment...')",
            "h1:has-text('Access denied')",
            "h1:has-text('Please verify')",
        ]
        for selector in captcha_selectors:
            try:
                locator = page.locator(selector).first
                if await locator.is_visible(timeout=3000):
                    if not self.headless:
                        _play_alert()
                        print(f"\n{'='*60}")
                        print(f"  🛑  CAPTCHA / BOT CHALLENGE DETECTED  🛑")
                        print(f"  URL: {page.url[:80]}")
                        print(f"  ➤ Please solve it in the Chromium window.")
                        print(f"  ➤ The scraper will auto-resume once cleared.")
                        print(f"{'='*60}\n")
                        page.set_default_timeout(120_000)
                        max_wait = 120
                        elapsed = 0
                        while elapsed < max_wait:
                            try:
                                still_visible = await locator.is_visible(timeout=2000)
                            except Exception:
                                still_visible = False
                            if not still_visible:
                                break
                            await asyncio.sleep(2)
                            elapsed += 2
                        print(f"  ✅  CAPTCHA cleared! Resuming...\n")
                        page.set_default_timeout(45_000)
                        try:
                            await page.wait_for_load_state("networkidle", timeout=10000)
                        except Exception:
                            pass
                        await page.wait_for_timeout(2000)
                    else:
                        # Headless: do NOT wait — skip immediately after 5s
                        logger.warning(f"CAPTCHA in headless mode on {page.url[:60]}. Skipping after 5s.")
                        await asyncio.wait_for(page.wait_for_timeout(5000), timeout=8)
                    break
            except asyncio.TimeoutError:
                break
            except Exception:
                continue

    # ─────────────────────────────────────────────────────────────
    # Popup / Cookie / Newsletter Dismissal (Site-Aware)
    # ─────────────────────────────────────────────────────────────

    async def _dismiss_popups(self, page, site_name: str = ""):
        """
        Comprehensive overlay dismissal.
        Uses a priority list of selectors tuned for all 34 target sites.
        """
        # ── Site-specific first-pass ──
        site_lower = site_name.lower()

        # Upstream / Recharge (NHST Media) — GDPR consent wall
        if "upstream" in site_lower or "recharge" in site_lower:
            for sel in [
                "button:has-text('Accept all')",
                "button:has-text('Confirm selection')",
                "button.accept-all",
                "#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll",
            ]:
                if await self._try_click(page, sel):
                    await page.wait_for_timeout(1500)
                    break

        # Bloomberg — metered paywall login nag
        if "bloomberg" in site_lower:
            await self._try_click(page, "button[data-testid='accept-button']")

        # Energy News Bulletin — GDPR + "Future of Energy" popup
        if "energy news bulletin" in site_lower:
            await self._try_click(page, "button:has-text('AGREE')")
            await page.wait_for_timeout(1000)
            await self._try_click(page, ".fancybox-close-small, button.fancybox-close, [aria-label='Close dialog']")

        # AccessNewswire — cookie consent
        if "accessnewswire" in site_lower:
            await self._try_click(page, "button:has-text('Accept')")

        # ── Universal pass — works for most sites ──
        universal_selectors = [
            # Cookie consent buttons
            "button[id*='accept']",
            "button[id*='consent']",
            "button[class*='accept']",
            "button[class*='consent']",
            "button[class*='agree']",
            "a[id*='accept']",
            "[aria-label*='Accept']",
            "[aria-label*='accept']",
            "button:has-text('Accept all')",
            "button:has-text('Accept All')",
            "button:has-text('Accept Cookies')",
            "button:has-text('Accept')",
            "button:has-text('I Agree')",
            "button:has-text('I agree')",
            "button:has-text('Agree')",
            "button:has-text('Got it')",
            "button:has-text('OK')",
            "button:has-text('Allow')",
            "button:has-text('Allow All')",
            "button:has-text('Continue')",
            "button:has-text('Confirm')",
            # Newsletter / modal close buttons
            "button:has-text('Close')",
            "button:has-text('No Thanks')",
            "button:has-text('No, thanks')",
            "button:has-text('Maybe Later')",
            "button:has-text('Dismiss')",
            "button:has-text('Skip')",
            "button[class*='close']",
            "button[aria-label='Close']",
            "button[aria-label='close']",
            "[class*='close-button']",
            "[class*='closeButton']",
            ".modal-close",
            ".popup-close",
            "a[class*='close']",
            "span[class*='close']",
            ".modal button:first-child",
            # GDPR IAB consent
            "#onetrust-accept-btn-handler",
            ".cc-accept",
            ".cc-btn.cc-allow",
            "#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll",
        ]
        for sel in universal_selectors:
            if await self._try_click(page, sel):
                await page.wait_for_timeout(600)
                break  # Only dismiss one; re-check if more appear

        # Final fallback — press Escape to close any remaining modal
        try:
            await page.keyboard.press("Escape")
            await page.wait_for_timeout(300)
        except Exception:
            pass

    async def _try_click(self, page, selector: str) -> bool:
        """Attempt to click a selector. Returns True if clicked."""
        try:
            btn = page.locator(selector).first
            if await btn.is_visible(timeout=500):
                await btn.click(timeout=2000)
                logger.debug(f"Dismissed overlay via: {selector}")
                return True
        except Exception:
            pass
        return False

    # ─────────────────────────────────────────────────────────────
    # Pagination Handlers
    # ─────────────────────────────────────────────────────────────

    async def _handle_load_more(self, page, selector: str | None, max_clicks: int) -> str:
        """
        Click 'Load More' up to max_clicks times.
        Dismisses popups that may appear between clicks (e.g. newsletter nag).
        """
        if not selector:
            selector = (
                "button.load-more, a.load-more, [class*='load-more'], "
                "button:has-text('Load More'), button:has-text('Load more'), "
                "a:has-text('Load More'), [class*='loadmore']"
            )
        for i in range(max_clicks):
            try:
                # Re-dismiss popups that may appear after loading more
                if i > 0:
                    await self._dismiss_popups(page)
                btn = page.locator(selector).first
                if not await btn.is_visible(timeout=3000):
                    break
                await btn.scroll_into_view_if_needed()
                await btn.click(timeout=5000)
                # Wait for network to settle after new content loads
                try:
                    await page.wait_for_load_state("networkidle", timeout=6000)
                except Exception:
                    await page.wait_for_timeout(random.randint(2500, 4000))
            except Exception:
                break
        return await page.content()

    async def _handle_infinite_scroll(self, page, max_scrolls: int) -> str:
        """
        Scroll to bottom, detect new content loading, repeat.
        Enforces a minimum of 6 scrolls for aggregator feeds (Newsfilter, Yahoo, AccessNewswire).
        """
        max_scrolls = max(max_scrolls, 6)
        prev_height = 0
        no_change_count = 0
        for i in range(max_scrolls):
            if i % 3 == 0:
                logger.info(f"   ... still scrolling ({i+1}/{max_scrolls})")
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            wait_ms = random.randint(3000, 5000)
            await page.wait_for_timeout(wait_ms)
            new_height = await page.evaluate("document.body.scrollHeight")
            if new_height == prev_height:
                no_change_count += 1
                if no_change_count >= 2:
                    # Two consecutive no-change scrolls = end of feed
                    break
            else:
                no_change_count = 0
            prev_height = new_height
        return await asyncio.wait_for(page.content(), timeout=20)

    async def _handle_next_page(self, page, selector: str | None, max_pages: int, base_url: str) -> str:
        """
        Navigate through paginated listing pages by clicking the 'Next' link.
        Collects combined HTML from all pages.
        """
        if not selector:
            selector = "a[rel='next'], a.next, a.pagination-next, li.next a, a:has-text('Next')"
        combined_html = await page.content()
        for _ in range(1, max_pages):
            try:
                # Re-dismiss popups that may have appeared after each page load
                await self._dismiss_popups(page)
                link = page.locator(selector).first
                if not await link.is_visible(timeout=3000):
                    break
                await link.click(timeout=6000)
                try:
                    await page.wait_for_load_state("networkidle", timeout=8000)
                except Exception:
                    await page.wait_for_load_state("domcontentloaded", timeout=5000)
                await page.wait_for_timeout(random.randint(1500, 3000))
                combined_html += "\n<!-- PAGE_BREAK -->\n" + await page.content()
            except Exception:
                break
        return combined_html
