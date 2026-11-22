"""Rendered-page evidence: first-screen screenshots (every module) and computed styles of text blocks (module 2).

Screenshots show only what the visitor sees on arrival, without scrolling - desktop 1366x768 and mobile 390x844
(2x pixel density, so small print stays legible) - as PNG. The cookie banner is accepted first (known consent
platforms, then a button labelled "Akceptuj" / "Accept all" ..., also inside iframes) so the screenshot shows the
content; what was clicked is kept in `raw.consent` (None = no banner found). The scraper only records facts; judging
them belongs to the analytic module.
"""

import hashlib
import re
from dataclasses import dataclass, field

from app.log import log

VIEWPORTS = {
    "desktop": {"viewport": {"width": 1366, "height": 768}},
    "mobile": {"viewport": {"width": 390, "height": 844}, "is_mobile": True, "has_touch": True,
               "device_scale_factor": 2},
}
MAX_BLOCKS = 200

# "accept all" buttons of common consent platforms (CSS also pierces open shadow roots, e.g. Usercentrics)
CONSENT_SELECTORS = (
    "#onetrust-accept-btn-handler",  # OneTrust
    "#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll", "#CybotCookiebotDialogBodyButtonAccept",  # Cookiebot
    "#didomi-notice-agree-button",  # Didomi
    ".qc-cmp2-summary-buttons button[mode='primary']",  # Quantcast
    "[data-testid='uc-accept-all-button']",  # Usercentrics
    ".cky-btn-accept", ".cmplz-accept", ".osano-cm-accept-all", "#truste-consent-button",  # CookieYes, Complianz...
    ".cc-allow", ".cc-accept-all", ".cm-btn-accept-all", ".klaro .cm-btn-success",  # cookieconsent, Klaro
    "#cookie-law-info-bar #cookie_action_close_header", ".fc-cta-consent",  # GDPR Cookie Consent, Google Funding Choices
    "button[data-cookiefirst-action='accept']", "#accept-all-cookies", "#acceptAllCookies", "#cookies-accept-all",
)
# button / link text of an "accept" action, whole label only ("Akceptuj wszystkie", "Accept all cookies", "Zgadzam się")
CONSENT_TEXT = re.compile(
    r"^\s*(akceptuj[eę]?|zaakceptuj|akceptuje|zgadzam si[eę]|wyra[zż]am zgod[eę]|zgoda|zezw[oó]l|przejd[zź] do serwisu"
    r"|accept|allow|agree|i agree|got it|alle akzeptieren|akzeptieren|ok)"
    r"(\s+(wszystkie|wszystko|all|cookies?|ciasteczka|pliki|plik[oó]w|i zamknij|and close|and continue|zgody))*"
    r"\s*[.!]?\s*$",
    re.IGNORECASE,
)


def accept_cookies(page) -> str | None:
    """Click the "accept" button of a cookie banner; returns what was clicked, None when nothing was found."""
    frames = [page.main_frame] + [f for f in page.frames if f is not page.main_frame][:10]
    for frame in frames:
        for sel in CONSENT_SELECTORS:
            try:
                loc = frame.locator(sel).first
                if loc.count() and loc.is_visible():
                    loc.click(timeout=3000)
                    return sel
            except Exception:  # noqa: S112 (best effort: a selector that fails just lets the next one try)
                continue
    for frame in frames:
        for role in ("button", "link"):
            try:
                if (hit := _click_first(frame.get_by_role(role, name=CONSENT_TEXT))) is not None:
                    return f"{role}: {hit}"
            except Exception:  # noqa: S112 (best effort: a selector that fails just lets the next one try)
                continue
    for frame in frames:  # clickable <div> / <span> without a button role
        try:
            if (hit := _click_first(frame.get_by_text(CONSENT_TEXT))) is not None:
                return f"text: {hit}"
        except Exception:  # noqa: S112 (best effort, see above)
            continue
    return None


def _click_first(loc) -> str | None:
    for i in range(min(loc.count(), 5)):
        el = loc.nth(i)
        if el.is_visible():
            label = (el.inner_text(timeout=1000) or "").strip()
            el.click(timeout=3000)
            return label
    return None

# Runs in the page. Visible text is summed per font size (-> dominant size of the material); blocks that mention
# risk or profit are recorded with their style, position and visibility.
LAYOUT_JS = r"""
() => {
  const RISK = /ryzyk|strat|traci|utrat|ostrze|nie gwarant|nie stanowi|cfd|dźwigni|dzwigni|kapitał.{0,40}(zagro|ryzyk)/i;
  const PROFIT = /zysk|zarab|zwrot|rentown|bonus|premi|oprocentowan|darmow|bez prowizji|gratis|\d+\s?%|\d+\s?zł/i;
  const transparent = c => !c || c === 'transparent' || /rgba\(.*,\s*0\)$/.test(c);
  // nearest opaque ancestor colour; a background image on the way makes the colour unreliable for contrast
  const background = el => {
    let image = false;
    for (let e = el; e; e = e.parentElement) {
      const cs = getComputedStyle(e);
      if (cs.backgroundImage && cs.backgroundImage !== 'none') image = true;
      if (!transparent(cs.backgroundColor)) return [cs.backgroundColor, image];
    }
    return ['rgb(255, 255, 255)', image];
  };
  const sizes = {};
  const blocks = [];
  const seen = new Set();
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  while (walker.nextNode()) {
    const node = walker.currentNode;
    const own = node.textContent.replace(/\s+/g, ' ').trim();
    const el = node.parentElement;
    if (own.length < 2 || !el || ['SCRIPT', 'STYLE', 'NOSCRIPT', 'TEMPLATE'].includes(el.tagName)) continue;
    const cs = getComputedStyle(el);
    const r = el.getBoundingClientRect();
    const visible = cs.display !== 'none' && cs.visibility !== 'hidden' && parseFloat(cs.opacity) > 0.05
      && r.width > 1 && r.height > 1;
    const fs = parseFloat(cs.fontSize);
    if (visible) sizes[fs] = (sizes[fs] || 0) + own.length;
    if (seen.has(el) || blocks.length >= MAX_BLOCKS) continue;
    seen.add(el);
    let text = (el.innerText || own).replace(/\s+/g, ' ').trim();
    if (text.length > 1000) text = own;
    const risk = RISK.test(text), profit = PROFIT.test(text);
    if (!risk && !profit) continue;
    const y = r.top + window.scrollY;
    const [bg, bgImage] = background(el);
    blocks.push({
      text: text.slice(0, 600), risk, profit, tag: el.tagName.toLowerCase(),
      font_size: fs, font_weight: cs.fontWeight, color: cs.color, background: bg, background_image: bgImage,
      opacity: parseFloat(cs.opacity), visible,
      x: Math.round(r.left + window.scrollX), y: Math.round(y), w: Math.round(r.width), h: Math.round(r.height),
      above_fold: visible && y < window.innerHeight,
      in_footer: !!el.closest('footer, [class*="footer"], [id*="footer"]'),
      in_disclaimer: !!el.closest('[class*="legal"], [class*="disclaimer"], [class*="risk"], [id*="disclaimer"]'),
      collapsed: !!el.closest('details:not([open]), [aria-expanded="false"], [hidden]'),
      in_link: !!el.closest('a'),
    });
  }
  let dominant = null, best = 0;
  for (const [k, v] of Object.entries(sizes)) if (v > best) { best = v; dominant = parseFloat(k); }
  return {
    viewport: {w: window.innerWidth, h: window.innerHeight},
    page_height: document.documentElement.scrollHeight,
    dominant_font_size: dominant,
    font_size_chars: sizes,
    blocks,
  };
}
""".replace("MAX_BLOCKS", str(MAX_BLOCKS))


@dataclass
class Capture:
    html: str | None = None  # desktop DOM after JS
    final_url: str | None = None  # desktop URL after redirects
    screenshots: list[tuple[str, bytes]] = field(default_factory=list)  # (viewport, png of the first screen)
    layout: dict = field(default_factory=dict)  # viewport -> LAYOUT_JS result
    consent: dict = field(default_factory=dict)  # viewport -> what accepted the cookie banner (None: no banner found)


def capture(browser, url: str, user_agent: str, with_layout: bool = False) -> Capture:
    """Render `url` in every viewport; failures of one viewport do not stop the others."""
    out = Capture()
    for name, opts in VIEWPORTS.items():
        ctx = browser.new_context(user_agent=user_agent, locale="pl-PL", **opts)
        try:
            page = ctx.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=30_000)
            try:
                page.wait_for_load_state("networkidle", timeout=10_000)
            except Exception:  # noqa: S110 (pages with endless polling never go idle)
                pass
            out.consent[name] = accept_cookies(page)
            if out.consent[name] is None:  # some consent platforms load the banner a few seconds late
                page.wait_for_timeout(2500)
                out.consent[name] = accept_cookies(page)
            if out.consent[name]:
                page.wait_for_timeout(1200)  # banner close animation, content re-layout
                page.evaluate("window.scrollTo(0, 0)")
            out.screenshots.append((name, page.screenshot(type="png", full_page=False)))  # first screen only
            if with_layout:
                out.layout[name] = page.evaluate(LAYOUT_JS)
            if name == "desktop":
                out.html, out.final_url = page.content(), page.url
        except Exception as exc:
            log.warning("layout_capture_failed", url=url, viewport=name, error=str(exc)[:300])
        finally:
            ctx.close()
    return out


def screenshot_id(viewport: str, text: str) -> str:
    """Media.source_url of a screenshot. Keyed by the page text, not the image bytes: carousels and banners
    change every render, so a new screenshot is stored only when the page text (a new version) changes."""
    return f"screenshot:{viewport}:{hashlib.sha256(text.encode()).hexdigest()[:16]}"
