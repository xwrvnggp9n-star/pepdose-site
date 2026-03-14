#!/usr/bin/env python3
"""
pep-dose.com — Static Site Builder
===================================
Converts the WordPress static export into a clean, themeable site.

USAGE:
    python3 build.py

OUTPUT:
    _dist/   (deploy this folder to any static host)

TO RETHEME:
    1. Edit _theme/config.json  — change colors, logo, site name, navigation
    2. Run python3 build.py     — rebuilds all pages

WHAT THIS DOES:
    - Strips WordPress boilerplate (emoji JS, wp-staging, wp-json API links, etc.)
    - Replaces hardcoded color values with your theme colors
    - Replaces logo images and site name text
    - Fixes navigation to work without the WordPress REST API
    - Makes all internal URLs relative (works on any domain)
    - Copies wp-content/uploads images + wp-includes CSS locally
    - Outputs clean HTML to _dist/
"""

import json
import os
import re
import shutil
from pathlib import Path

# ─────────────────────────────────────────────────────────────────────────────
# Paths
# ─────────────────────────────────────────────────────────────────────────────
BASE       = Path(__file__).parent
THEME_DIR  = BASE / '_theme'
DIST_DIR   = BASE / '_dist'
CONFIG_FILE = THEME_DIR / 'config.json'
THEME_CSS   = THEME_DIR / 'theme.css'

# ─────────────────────────────────────────────────────────────────────────────
# Load config
# ─────────────────────────────────────────────────────────────────────────────
with open(CONFIG_FILE, encoding='utf-8') as f:
    C = json.load(f)

SITE_NAME  = C['site_name']
SITE_URL   = C.get('site_url', 'https://pep-dose.com')
LOGO       = C['logo']
FAVICONS   = C['favicon']
FONTS      = C['fonts']
COLORS     = C['colors']
NAV_ITEMS  = C.get('nav', [])
FOOTER_CFG = C.get('footer', {})
ANALYTICS  = C.get('analytics', {})

# ─────────────────────────────────────────────────────────────────────────────
# Color replacement: map original hardcoded colors → theme colors
# ─────────────────────────────────────────────────────────────────────────────
ORIGINAL_COLORS = {
    'primary_dark':    '#2c3e50',
    'primary_mid':     '#34495e',
    'primary_darkest': '#1a252f',
    'accent':          '#e74c3c',
    'secondary':       '#3498db',
    'header_text':     '#ecf0f1',
    'body_bg':         '#f9f9f9',
    'body_text':       '#333333',
}

def build_color_map():
    """Return {old_hex: new_hex} for colors that changed."""
    mapping = {}
    for key, old in ORIGINAL_COLORS.items():
        new = COLORS.get(key, old)
        if new.lower() != old.lower():
            mapping[old.lower()] = new
            mapping[old.upper()] = new
            # CSS shorthand sometimes uses 3-char hex — skip for now
    return mapping

COLOR_MAP = build_color_map()

def apply_colors(text):
    """Replace original hardcoded colors with theme colors."""
    for old, new in COLOR_MAP.items():
        text = text.replace(old, new)
    return text

# ─────────────────────────────────────────────────────────────────────────────
# URL helpers
# ─────────────────────────────────────────────────────────────────────────────
DOMAIN = 'https://pep-dose.com'

def fix_urls(text):
    """Make internal absolute URLs relative."""
    return text.replace(DOMAIN + '/', '/').replace(DOMAIN, '/')

def fix_logo_urls(text):
    """Replace logo src and site name spans in header/footer HTML."""
    # Replace logo img src
    old_logo = 'https://pep-dose.com/wp-content/uploads/2025/07/cropped-pdlogo-nr.png'
    new_logo = LOGO['img_url']
    text = text.replace(old_logo, new_logo)

    # Replace logo text spans
    old_span1 = '<span class="peptide">Peptide</span>'
    new_span1 = f'<span class="peptide">{LOGO["span_1"]}</span>'
    text = text.replace(old_span1, new_span1)

    old_span2 = '<span class="dosages">Dosages</span>'
    new_span2 = f'<span class="dosages">{LOGO["span_2"]}</span>'
    text = text.replace(old_span2, new_span2)

    return text

# ─────────────────────────────────────────────────────────────────────────────
# HTML helpers
# ─────────────────────────────────────────────────────────────────────────────
def extract(pattern, text, group=1, flags=re.DOTALL):
    m = re.search(pattern, text, flags)
    return m.group(group) if m else ''

def strip_wp_head(head):
    """Remove WordPress boilerplate from <head> content."""
    # wp-emoji (large inline script + style)
    head = re.sub(r'<script[^>]*>.*?_wpemojiSettings.*?</script>', '', head, flags=re.DOTALL)
    head = re.sub(r"<style[^>]*id='wp-emoji-styles[^']*'[^>]*>.*?</style>", '', head, flags=re.DOTALL)
    head = re.sub(r"<style[^>]*>img\.wp-smiley.*?</style>", '', head, flags=re.DOTALL)

    # wp-staging
    head = re.sub(r'<script[^>]*wpstg[^>]*>.*?</script>', '', head, flags=re.DOTALL)
    head = re.sub(r'<script[^>]*wpstg[^>]*>', '', head)

    # wp-json discovery links + xmlrpc + EditURI + oEmbed
    head = re.sub(r'<link[^>]*api\.w\.org[^>]*/>', '', head)
    head = re.sub(r'<link[^>]*wp-json[^>]*/>', '', head)
    head = re.sub(r'<link[^>]*xmlrpc\.php[^>]*/>', '', head)
    head = re.sub(r'<link[^>]*EditURI[^>]*/>', '', head)
    head = re.sub(r'<link[^>]*oEmbed[^>]*/>', '', head)
    head = re.sub(r'<link[^>]*type="application/json\+oembed"[^>]*/>', '', head)
    head = re.sub(r'<link[^>]*type="text/xml\+oembed"[^>]*/>', '', head)

    # WordPress generator meta + shortlink
    head = re.sub(r'<meta[^>]*name="generator"[^>]*/>', '', head)
    head = re.sub(r'<link[^>]*shortlink[^>]*/>', '', head)

    # Yoast SEO comments
    head = re.sub(r'<!-- This site is optimized with the Yoast.*?-->', '', head, flags=re.DOTALL)
    head = re.sub(r'<!-- / Yoast SEO.*?-->', '', head)

    # External WP resources (we'll load local copies)
    head = re.sub(r"<link[^>]*id='wp-block-library-css'[^>]*/>\s*", '', head)
    head = re.sub(r"<style[^>]*id='classic-theme-styles-inline-css'[^>]*>.*?</style>\s*", '', head, flags=re.DOTALL)
    head = re.sub(r"<style[^>]*id='filebird-block-filebird-gallery-style-inline-css'[^>]*>.*?</style>\s*", '', head, flags=re.DOTALL)
    head = re.sub(r"<style[^>]*id='global-styles-inline-css'[^>]*>.*?</style>\s*", '', head, flags=re.DOTALL)

    # External contact-form-7 CSS
    head = re.sub(r"<link[^>]*contact-form-7[^>]*/>\s*", '', head)

    # The large shared header/footer inline CSS (we serve it as theme.css)
    head = re.sub(r'<style>\s*/\*{4,}\s*\*\s*ENHANCED HEADER STYLES.*?</style>', '', head, flags=re.DOTALL)

    # FontAwesome + Google Fonts (keep, but they'll be re-added in our template)
    head = re.sub(r'<link[^>]*font-awesome[^>]*/>\s*', '', head)
    head = re.sub(r'<link[^>]*fonts\.googleapis\.com[^>]*/>\s*', '', head)

    # Stray inline size hint
    head = re.sub(r"<style>img:is.*?</style>", '', head, flags=re.DOTALL)

    return head.strip()

# ─────────────────────────────────────────────────────────────────────────────
# Navigation HTML builders
# ─────────────────────────────────────────────────────────────────────────────
def build_desktop_nav(items):
    parts = []
    for item in items:
        kids = item.get('children', [])
        if kids:
            kid_html = '\n'.join(
                f'          <li role="none"><a href="{k["url"]}" role="menuitem">{k["title"]}</a></li>'
                for k in kids
            )
            multi = ' multi-column' if len(kids) > 15 else ''
            parts.append(f'''\
        <li class="has-dropdown">
          <a href="{item["url"]}" role="button" aria-expanded="false" aria-haspopup="true">{item["title"]}</a>
          <ul class="dropdown-menu{multi}" role="menu">
{kid_html}
          </ul>
        </li>''')
        else:
            parts.append(f'        <li><a href="{item["url"]}">{item["title"]}</a></li>')
    return '\n'.join(parts)


def build_mobile_nav(items):
    parts = []
    for item in items:
        kids = item.get('children', [])
        parts.append(f'        <li>')
        parts.append(f'          <a href="{item["url"]}">{item["title"]}</a>')
        if kids:
            parts.append('          <ul class="mobile-sub-nav">')
            for k in kids:
                parts.append(f'            <li><a href="{k["url"]}">{k["title"]}</a></li>')
            parts.append('          </ul>')
        parts.append('        </li>')
    return '\n'.join(parts)


def build_footer_links(links):
    return '\n'.join(
        f'            <li><a href="{lnk["url"]}">{lnk["title"]}</a></li>'
        for lnk in links
    )

# ─────────────────────────────────────────────────────────────────────────────
# Page template
# ─────────────────────────────────────────────────────────────────────────────
def build_head(title, meta_desc, canonical, og_image, schema, custom_css_text,
               og_extras=None):
    """Build the <head> section with full SEO meta tags, analytics, and performance hints."""
    if og_extras is None:
        og_extras = {}

    font_link = f'<link href="{FONTS["google_url"]}&display=swap" rel="stylesheet"/>' if FONTS.get('google_url') else ''
    custom_css_block = f'\n    <style id="wp-custom-css">{custom_css_text}</style>' if custom_css_text.strip() else ''
    canon_tag = f'\n    <link rel="canonical" href="{fix_urls(canonical)}" />' if canonical else ''

    # OG image tags (image + width + height + type)
    og_image_tags = ''
    if og_image:
        og_image_tags = f'\n    <meta property="og:image" content="{fix_urls(og_image)}" />'
        if og_extras.get('og_image_width'):
            og_image_tags += f'\n    <meta property="og:image:width" content="{og_extras["og_image_width"]}" />'
        if og_extras.get('og_image_height'):
            og_image_tags += f'\n    <meta property="og:image:height" content="{og_extras["og_image_height"]}" />'
        if og_extras.get('og_image_type'):
            og_image_tags += f'\n    <meta property="og:image:type" content="{og_extras["og_image_type"]}" />'

    # Extra OG/Twitter/article meta tags
    og_locale = og_extras.get('og_locale', 'en_US')
    og_site_name = og_extras.get('og_site_name', SITE_NAME)
    og_type = og_extras.get('og_type', 'website')
    og_url = fix_urls(og_extras.get('og_url', canonical or ''))
    twitter_card = og_extras.get('twitter_card', 'summary_large_image')

    article_times = ''
    if og_extras.get('article_published'):
        article_times += f'\n    <meta property="article:published_time" content="{og_extras["article_published"]}" />'
    if og_extras.get('article_modified'):
        article_times += f'\n    <meta property="article:modified_time" content="{og_extras["article_modified"]}" />'

    # Analytics (GA4 + Search Console verification)
    analytics_tags = ''
    ga4_id = ANALYTICS.get('ga4_id', '')
    sc_verify = ANALYTICS.get('search_console_verification', '')
    if sc_verify:
        analytics_tags += f'\n    <meta name="google-site-verification" content="{sc_verify}" />'
    if ga4_id:
        analytics_tags += f'''
    <script async src="https://www.googletagmanager.com/gtag/js?id={ga4_id}"></script>
    <script>
      window.dataLayer = window.dataLayer || [];
      function gtag(){{dataLayer.push(arguments);}}
      gtag('js', new Date());
      gtag('config', '{ga4_id}');
    </script>'''

    return f'''\
<!DOCTYPE html>
<html lang="en-US">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name='robots' content='index, follow, max-image-preview:large, max-snippet:-1, max-video-preview:-1' />
    <title>{title}</title>
    <meta name="description" content="{meta_desc}" />{canon_tag}
    <meta property="og:locale" content="{og_locale}" />
    <meta property="og:type" content="{og_type}" />
    <meta property="og:title" content="{title}" />
    <meta property="og:description" content="{meta_desc}" />
    <meta property="og:url" content="{og_url}" />
    <meta property="og:site_name" content="{og_site_name}" />{og_image_tags}{article_times}
    <meta name="twitter:card" content="{twitter_card}" />
    <meta name="twitter:title" content="{title}" />
    <meta name="twitter:description" content="{meta_desc}" />
    {fix_urls(schema)}{analytics_tags}
    <link rel="icon" href="{FAVICONS['32x32']}" sizes="32x32" />
    <link rel="icon" href="{FAVICONS['192x192']}" sizes="192x192" />
    <link rel="apple-touch-icon" href="{FAVICONS['apple_touch']}" />
    <meta name="msapplication-TileImage" content="{FAVICONS['mstile']}" />
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link rel="preconnect" href="https://cdnjs.cloudflare.com">
    {font_link}
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css" media="print" onload="this.media='all'"/>
    <noscript><link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css"/></noscript>
    <link rel="stylesheet" href="/theme/theme.css"/>
    <link rel="stylesheet" href="/wp-includes/css/dist/block-library/style.min.css"/>{custom_css_block}
</head>'''


def build_header():
    desktop_nav = build_desktop_nav(NAV_ITEMS)
    mobile_nav  = build_mobile_nav(NAV_ITEMS)
    logo_url    = LOGO['img_url']
    logo_alt    = LOGO['img_alt']
    span1       = LOGO['span_1']
    span2       = LOGO['span_2']

    return f'''\
<body>

<!-- Skip to content -->
<a href="#main-content" class="skip-link">Skip to content</a>

<!-- Progress Bar -->
<div class="progress-bar" id="progressBar" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0"></div>

<!-- Mobile Search Overlay -->
<div class="mobile-search-overlay" id="mobileSearchOverlay">
  <form role="search" method="get" action="/" class="mobile-search-form">
    <input type="search" class="mobile-search-input" placeholder="Search protocols, articles..." name="s" required>
    <button type="submit" class="mobile-search-submit"><i class="fas fa-search"></i></button>
  </form>
</div>

<!-- Mobile Overlay -->
<div class="mobile-overlay" id="mobileOverlay" aria-hidden="true"></div>

<!-- SITE HEADER -->
<header class="site-header" id="siteHeader" role="banner">
  <div class="header-inner">
    <button class="hamburger-btn" id="mobileHamburgerBtn" aria-label="Toggle navigation menu" aria-expanded="false">
      <i class="fas fa-bars" aria-hidden="true"></i>
    </button>

    <a href="/" class="header-logo" aria-label="{SITE_NAME} - Home">
      <div class="header-logo-text">
        <span class="peptide">{span1}</span>
        <span class="sep">&middot;</span>
        <span class="dosages">{span2}</span>
      </div>
    </a>

    <nav class="main-nav" role="navigation" aria-label="Main navigation">
      <ul>
{desktop_nav}
      </ul>
    </nav>

    <div class="header-search">
      <form role="search" method="get" action="/" class="header-search-form">
        <div class="header-search-wrapper">
          <input type="search" class="header-search-input" placeholder="Search" name="s" required>
        </div>
      </form>
    </div>

    <button class="mobile-search-toggle" id="mobileSearchToggle" aria-label="Toggle search">
      <i class="fas fa-search"></i>
    </button>
  </div>

  <nav class="mobile-nav-panel" id="mobileNavPanel" role="navigation" aria-label="Mobile navigation">
    <div class="mobile-nav-panel-inner">
      <div class="mobile-nav-search">
        <form role="search" method="get" action="/">
          <input type="search" placeholder="Search..." name="s" required>
          <button type="submit"><i class="fas fa-search"></i></button>
        </form>
      </div>
      <ul class="mobile-nav-list">
{mobile_nav}
      </ul>
    </div>
  </nav>
</header>

<!-- HEADER JS (scroll effects, mobile menu toggle) -->
<script>
(function() {{
  'use strict';

  var header   = document.getElementById('siteHeader');
  var hamburger = document.getElementById('mobileHamburgerBtn');
  var mobilePanel = document.getElementById('mobileNavPanel');
  var overlay  = document.getElementById('mobileOverlay');
  var mobileSearchToggle = document.getElementById('mobileSearchToggle');
  var mobileSearchOverlay = document.getElementById('mobileSearchOverlay');
  var progressBar = document.getElementById('progressBar');

  // Scroll shrink
  window.addEventListener('scroll', function() {{
    if (window.scrollY > 50) {{
      header.classList.add('scrolled');
    }} else {{
      header.classList.remove('scrolled');
    }}
    // Progress bar
    var pct = (window.scrollY / (document.body.scrollHeight - window.innerHeight)) * 100;
    if (progressBar) progressBar.style.width = pct + '%';
  }});

  // Mobile menu
  function closeMobileMenu() {{
    mobilePanel.classList.remove('open');
    overlay.classList.remove('visible');
    overlay.setAttribute('aria-hidden', 'true');
    hamburger.setAttribute('aria-expanded', 'false');
    document.body.style.overflow = '';
  }}

  if (hamburger) {{
    hamburger.addEventListener('click', function() {{
      var open = mobilePanel.classList.toggle('open');
      overlay.classList.toggle('visible', open);
      overlay.setAttribute('aria-hidden', String(!open));
      hamburger.setAttribute('aria-expanded', String(open));
      document.body.style.overflow = open ? 'hidden' : '';
    }});
  }}

  if (overlay) overlay.addEventListener('click', closeMobileMenu);

  // Mobile search
  if (mobileSearchToggle) {{
    mobileSearchToggle.addEventListener('click', function() {{
      mobileSearchOverlay.classList.toggle('visible');
    }});
  }}

  // Desktop dropdowns
  document.querySelectorAll('.has-dropdown').forEach(function(li) {{
    var btn = li.querySelector('a[aria-haspopup]');
    var menu = li.querySelector('.dropdown-menu');
    if (!btn || !menu) return;
    li.addEventListener('mouseenter', function() {{
      menu.style.opacity = '1';
      menu.style.visibility = 'visible';
      menu.style.transform = 'translateX(-50%) translateY(0)';
      btn.setAttribute('aria-expanded', 'true');
    }});
    li.addEventListener('mouseleave', function() {{
      menu.style.opacity = '0';
      menu.style.visibility = 'hidden';
      menu.style.transform = 'translateX(-50%) translateY(10px)';
      btn.setAttribute('aria-expanded', 'false');
    }});
  }});

  // Back to top
  var btt = document.getElementById('backToTop');
  if (btt) {{
    window.addEventListener('scroll', function() {{
      btt.classList.toggle('visible', window.scrollY > 300);
    }});
    btt.addEventListener('click', function() {{
      window.scrollTo({{ top: 0, behavior: 'smooth' }});
    }});
  }}
}})();
</script>'''


def build_footer():
    tagline       = FOOTER_CFG.get('tagline', '')
    disclaimer    = FOOTER_CFG.get('disclaimer', '')
    explore_links = build_footer_links(FOOTER_CFG.get('explore_links', []))
    legal_links   = build_footer_links(FOOTER_CFG.get('legal_links', []))
    span1         = LOGO['span_1']
    span2         = LOGO['span_2']

    return f'''\
<footer class="site-footer" role="contentinfo">
  <div class="footer-wave"></div>
  <div class="footer-main">
    <div class="footer-container">
      <div class="footer-grid">

        <div class="footer-column footer-about">
          <div class="footer-logo">
            <span><span class="peptide">{span1}</span><span class="sep">&middot;</span><span class="dosages">{span2}</span></span>
          </div>
          <p class="footer-tagline">{tagline}</p>
        </div>

        <div class="footer-column">
          <h3>Explore</h3>
          <ul class="footer-links">
{explore_links}
          </ul>
        </div>

        <div class="footer-column">
          <h3>Legal</h3>
          <ul class="footer-links">
{legal_links}
          </ul>
        </div>

      </div>
    </div>
  </div>

  <div class="footer-bottom">
    <div class="footer-container">
      <div class="footer-bottom-content">
        <div class="footer-copyright">
          {disclaimer}
        </div>
      </div>
    </div>
  </div>
</footer>

<div class="back-to-top" id="backToTop" aria-label="Back to top">
  <i class="fas fa-arrow-up"></i>
</div>

<script>
  document.getElementById('currentYear').textContent = new Date().getFullYear();
</script>
<script src="/theme/search.js" defer></script>

</body>
</html>'''

# ─────────────────────────────────────────────────────────────────────────────
# Process a single HTML file
# ─────────────────────────────────────────────────────────────────────────────
def add_lazy_loading(html):
    """Add loading='lazy' to images, except the first one (LCP candidate)."""
    img_count = [0]
    def lazy_replace(match):
        img_count[0] += 1
        tag = match.group(0)
        # Skip first image (likely LCP element) and images that already have loading attr
        if img_count[0] == 1 or 'loading=' in tag:
            return tag
        if 'fetchpriority="high"' in tag:
            return tag
        return tag.replace('<img ', '<img loading="lazy" ')
    return re.sub(r'<img [^>]+/?>', lazy_replace, html)


def strip_sponsor_sections(text):
    """Remove White Market Peptides sponsor ad sections and external images."""
    text = re.sub(
        r'<section\s+id="recommended-source"[^>]*>.*?</section>',
        '', text, flags=re.DOTALL)
    # Remove product images hosted on the old sponsor's domain
    text = re.sub(
        r'<img[^>]*src="https?://whitemarketpeptides\.com/[^"]*"[^>]*/?>',
        '', text)
    return text


# ─────────────────────────────────────────────────────────────────────────────
# Sponsor backlink injection
# ─────────────────────────────────────────────────────────────────────────────
SPONSOR       = C.get('sponsor', {})
SPONSOR_LINKS = C.get('sponsor_links', {})
SPONSOR_NAME  = SPONSOR.get('name', 'White Market Peptides')
SPONSOR_URL   = SPONSOR.get('url', 'https://whitemarketpeptides.com')
SPONSOR_CODE  = SPONSOR.get('discount_code', 'PEPDOSE')
SPONSOR_DEAL  = SPONSOR.get('discount_text', '10% off + free 2-day shipping over $200')

_SLUG_TO_NAME = {
    'what-is-bpc-157':             'BPC-157',
    'what-is-ghk-cu-2':           'GHK-Cu',
    'what-is-tb-500':             'TB-500',
    'what-is-tesamorelin':        'Tesamorelin',
    'what-is-mots-c':            'MOTS-c',
    'what-is-glow-peptide-blend': 'GLOW',
    'what-is-klow-peptide-blend': 'KLOW',
    'what-is-the-wolverine-stack':'Wolverine Stack',
}


def derive_peptide_name(slug):
    """Convert a page slug like 'what-is-bpc-157' to a display name."""
    return _SLUG_TO_NAME.get(slug, slug.replace('what-is-', '').replace('-', ' ').title())


def inject_inline_sponsor_link(html, product_url, peptide_name):
    """Insert a contextual sponsor paragraph before the references section."""
    link = (
        f'<a href="{product_url}" rel="sponsored nofollow noopener" '
        f'target="_blank">{SPONSOR_NAME}</a>'
    )
    paragraph = (
        f'<p style="max-width:750px">Looking for research-grade {peptide_name}? '
        f'Our sponsor {link} carries {peptide_name} with third-party purity testing. '
        f'Use code <strong>{SPONSOR_CODE}</strong> for {SPONSOR_DEAL}.</p>'
    )
    # Insert before the auto-references section, or before </article> as fallback
    marker = '<section class="auto-references-section"'
    if marker in html:
        html = html.replace(marker, paragraph + '\n' + marker, 1)
    elif '</article>' in html:
        html = html.replace('</article>', paragraph + '\n</article>', 1)
    return html


def inject_sponsor_cta(html, product_url, peptide_name):
    """Insert a styled CTA block between references and post navigation."""
    cta = f'''<div class="sponsor-cta">
  <div class="sponsor-cta-badge">Sponsored</div>
  <div class="sponsor-cta-body">
    <div class="sponsor-cta-text">
      <strong>Get {peptide_name} from {SPONSOR_NAME}</strong>
      <span>Third-party tested &middot; Use code <strong>{SPONSOR_CODE}</strong> for {SPONSOR_DEAL}</span>
    </div>
    <a href="{product_url}" class="sponsor-cta-btn" rel="sponsored nofollow noopener" target="_blank">
      View Product &rarr;
    </a>
  </div>
</div>'''
    # Insert before post-navigation, or before </article> as fallback
    marker = '<div class="post-navigation">'
    if marker not in html:
        marker = '<div class="post-navigation"'
    if marker in html:
        html = html.replace(marker, cta + '\n' + marker, 1)
    elif '</article>' in html:
        html = html.replace('</article>', cta + '\n</article>', 1)
    return html


def sanitize_old_branding(text):
    """Replace old domain references that may linger in Yoast JSON-LD schema."""
    # Domain-level references only (safe — these are always the old brand)
    text = text.replace('PeptideDosage.com', SITE_NAME)
    text = text.replace('PeptideDosages.com', SITE_NAME)
    text = text.replace('peptidedosages.com', SITE_NAME)
    return text


def sanitize_author(text):
    """Remove personal email from author meta tags and schema JSON-LD."""
    text = text.replace('sec9vzion@outlook.com', 'Pep-Dose Staff')
    text = re.sub(
        r'"url"\s*:\s*"https?://pep-dose\.com/author/sec9vzionoutlook-com/?[^"]*"',
        '"url":"https://pep-dose.com/about-us/"',
        text,
    )
    # Strip <meta name="author" content="sec9vzion...">
    text = re.sub(
        r'<meta\s+name="author"\s+content="sec9vzion[^"]*"\s*/?>',
        '<meta name="author" content="Pep-Dose Staff" />',
        text,
    )
    return text


def process_file(src_path, dst_path):
    with open(src_path, 'r', errors='replace') as f:
        raw = f.read()

    # ── Extract head fields ───────────────────────────────────────────────────
    head_html = extract(r'<head>(.*?)</head>', raw)
    title     = extract(r'<title>(.*?)</title>', head_html)
    meta_desc = extract(r'<meta\s+name="description"\s+content="([^"]*)"', head_html, flags=0)
    canonical = extract(r'<link\s+rel=["\']canonical["\']\s+href="([^"]*)"', head_html, flags=0)
    og_image  = extract(r'<meta\s+property="og:image"\s+content="([^"]*)"', head_html, flags=0)
    schema    = extract(r'(<script type="application/ld\+json"[^>]*>.*?</script>)', head_html)

    # Extract additional OG/Twitter/article meta tags
    og_extras = {
        'og_locale':         extract(r'<meta\s+property="og:locale"\s+content="([^"]*)"', head_html, flags=0) or 'en_US',
        'og_site_name':      extract(r'<meta\s+property="og:site_name"\s+content="([^"]*)"', head_html, flags=0) or SITE_NAME,
        'og_type':           extract(r'<meta\s+property="og:type"\s+content="([^"]*)"', head_html, flags=0) or 'website',
        'og_url':            extract(r'<meta\s+property="og:url"\s+content="([^"]*)"', head_html, flags=0) or canonical,
        'twitter_card':      extract(r'<meta\s+name="twitter:card"\s+content="([^"]*)"', head_html, flags=0) or 'summary_large_image',
        'article_published': extract(r'<meta\s+property="article:published_time"\s+content="([^"]*)"', head_html, flags=0),
        'article_modified':  extract(r'<meta\s+property="article:modified_time"\s+content="([^"]*)"', head_html, flags=0),
        'og_image_width':    extract(r'<meta\s+property="og:image:width"\s+content="([^"]*)"', head_html, flags=0),
        'og_image_height':   extract(r'<meta\s+property="og:image:height"\s+content="([^"]*)"', head_html, flags=0),
        'og_image_type':     extract(r'<meta\s+property="og:image:type"\s+content="([^"]*)"', head_html, flags=0),
    }

    # Page-specific custom CSS (from wp-custom-css block)
    custom_css = extract(r'<style[^>]*id="wp-custom-css"[^>]*>(.*?)</style>', head_html)

    # ── Sanitize author email + old branding ──────────────────────────────────
    schema = sanitize_author(schema)
    schema = sanitize_old_branding(schema)

    # ── Extract body ──────────────────────────────────────────────────────────
    body_html = extract(r'<body[^>]*>(.*?)</body>', raw)

    # Get the <main> block (contains all page-specific content + inline CSS)
    main_html = extract(r'(<main[^>]*>.*?</main>)', body_html)
    if not main_html:
        # Some WP exports omit </main>; grab from <main> to end of body
        main_html = extract(r'(<main[^>]*>.*)', body_html)
        if main_html:
            main_html += '</main>'
        else:
            main_html = '<main id="main-content"><p>Content unavailable.</p></main>'

    # ── Apply transformations ─────────────────────────────────────────────────
    main_html  = apply_colors(main_html)
    main_html  = fix_urls(main_html)
    main_html  = fix_logo_urls(main_html)
    main_html  = sanitize_old_branding(main_html)
    main_html  = strip_sponsor_sections(main_html)

    # Inject sponsor backlinks for pages with matching WMP products
    slug = src_path.parent.name
    product_url = SPONSOR_LINKS.get(slug)
    if product_url:
        peptide_name = derive_peptide_name(slug)
        main_html = inject_inline_sponsor_link(main_html, product_url, peptide_name)
        main_html = inject_sponsor_cta(main_html, product_url, peptide_name)

    main_html  = add_lazy_loading(main_html)
    custom_css = apply_colors(custom_css)

    # ── Assemble page ─────────────────────────────────────────────────────────
    head_section = build_head(title, meta_desc, canonical, og_image, schema, custom_css,
                              og_extras=og_extras)
    page = '\n'.join([
        head_section,
        build_header(),
        main_html,
        build_footer(),
    ])

    # ── Write output ──────────────────────────────────────────────────────────
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    with open(dst_path, 'w', encoding='utf-8') as f:
        f.write(page)

    return True

# ─────────────────────────────────────────────────────────────────────────────
# Discover all source pages
# ─────────────────────────────────────────────────────────────────────────────
SKIP_DIRS = {'_dist', '_theme', 'wp-json', '.claude', '.git', '__pycache__'}

# Files without .html extension that are actually HTML pages
BARE_HTML_FILES = [
    'about-us', 'contact-us', 'cookie-policy', 'disclaimer',
    'privacy-policy', 'terms-conditions',
    'peptide-stack-dosages',
    'retatrutide-5mg', 'retatrutide-10mg', 'retatrutide-30mg',
]

def iter_source_files():
    """Yield (src_path, dst_path) pairs for all processable HTML files."""

    # ── All index.html files (walk directories) ───────────────────────────────
    for root, dirs, files in os.walk(BASE):
        root = Path(root)
        rel  = root.relative_to(BASE)

        # Skip unwanted directories
        dirs[:] = [d for d in dirs
                   if d not in SKIP_DIRS
                   and not d.startswith('.')
                   and not d.startswith('index.html?')]  # skip WP ?p= dirs

        if 'index.html' in files:
            src = root / 'index.html'
            dst = DIST_DIR / rel / 'index.html'
            yield src, dst

    # ── Bare HTML files ───────────────────────────────────────────────────────
    for name in BARE_HTML_FILES:
        src = BASE / name
        if src.exists():
            # Serve them as /name/index.html so links work cleanly
            # (e.g. /about-us/ → _dist/about-us/index.html)
            dst = DIST_DIR / name / 'index.html'
            yield src, dst


# ─────────────────────────────────────────────────────────────────────────────
# Copy static assets
# ─────────────────────────────────────────────────────────────────────────────
def copy_assets():
    """Copy images and local CSS to _dist."""
    # wp-content/uploads  (all images)
    src_uploads = BASE / 'wp-content' / 'uploads'
    dst_uploads = DIST_DIR / 'wp-content' / 'uploads'
    if src_uploads.exists():
        if dst_uploads.exists():
            shutil.rmtree(dst_uploads)
        shutil.copytree(src_uploads, dst_uploads)
        print(f"  ✓  Copied wp-content/uploads/ → _dist/")

    # wp-includes/css/dist/block-library/style.min.css (filename may include ?ver= suffix)
    src_css_dir = BASE / 'wp-includes' / 'css' / 'dist' / 'block-library'
    dst_css = DIST_DIR / 'wp-includes' / 'css' / 'dist' / 'block-library' / 'style.min.css'
    if src_css_dir.exists():
        # Find any .css file in that directory
        css_candidates = list(src_css_dir.glob('*.css*'))
        if css_candidates:
            dst_css.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(css_candidates[0], dst_css)
            print(f"  ✓  Copied wp-includes block-library CSS")

    # theme/theme.css
    dst_theme = DIST_DIR / 'theme' / 'theme.css'
    dst_theme.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(THEME_CSS, dst_theme)
    print(f"  ✓  Copied theme/theme.css")


# ─────────────────────────────────────────────────────────────────────────────
# Search index generator
# ─────────────────────────────────────────────────────────────────────────────
def extract_text_from_html(html_string):
    """Strip HTML tags, scripts, styles and return plain text."""
    text = re.sub(r'<script[^>]*>.*?</script>', ' ', html_string, flags=re.DOTALL)
    text = re.sub(r'<style[^>]*>.*?</style>', ' ', html_string, flags=re.DOTALL)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = text.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
    text = text.replace('&#8211;', '-').replace('&#8212;', '--')
    text = text.replace('&nbsp;', ' ').replace('&#8217;', "'")
    text = text.replace('&middot;', ' ').replace('&#8230;', '...')
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def classify_page(url_path):
    """Return a page type string based on URL path."""
    if url_path == '/':
        return 'home'
    if '/single-peptide-dosages/' in url_path:
        return 'dosage'
    if '/peptide-blend-dosages/' in url_path:
        return 'dosage'
    if '/peptide-stack-dosages' in url_path:
        return 'dosage'
    if '/retatrutide' in url_path and 'what-is' not in url_path:
        return 'dosage'
    if url_path.startswith('/what-is-') or url_path.startswith('/what-are-'):
        return 'article'
    if '/category/' in url_path:
        return 'category'
    if '/blog/' in url_path:
        return 'blog'
    if '/dosages' in url_path:
        return 'index'
    if '/peptide-dosage-calculator' in url_path:
        return 'tool'
    if any(x in url_path for x in ['/about-us', '/contact-us']):
        return 'info'
    if any(x in url_path for x in ['/privacy-', '/cookie-', '/terms-', '/disclaimer']):
        return 'legal'
    if '/combine-peptides' in url_path or '/reconstitution' in url_path:
        return 'guide'
    return 'page'


def generate_search_index():
    """Generate search-index.json from all built HTML pages in _dist."""
    index = []

    for html_file in sorted(DIST_DIR.rglob('index.html')):
        rel = html_file.parent.relative_to(DIST_DIR)
        url_path = '/' if str(rel) == '.' else f'/{rel}/'

        with open(html_file, 'r', encoding='utf-8', errors='replace') as f:
            html = f.read()

        title = extract(r'<title>(.*?)</title>', html)
        title = title.replace('&#8211;', '-').replace('&amp;', '&')

        meta_desc = extract(
            r'<meta\s+name="description"\s+content="([^"]*)"', html, flags=0
        )

        main_block = extract(r'<main[^>]*>(.*?)</main>', html)
        content_text = extract_text_from_html(main_block) if main_block else ''
        content_snippet = content_text[:300] if content_text else ''

        page_type = classify_page(url_path)

        # Skip home page and pagination pages from search
        if page_type == 'home':
            continue
        if '/page/' in url_path:
            continue

        entry = {
            'url': url_path,
            'title': title,
            'description': meta_desc,
            'content': content_snippet,
            'type': page_type,
        }
        index.append(entry)

    index_path = DIST_DIR / 'search-index.json'
    with open(index_path, 'w', encoding='utf-8') as f:
        json.dump(index, f, ensure_ascii=False, separators=(',', ':'))

    print(f"\n  ✓  search-index.json generated with {len(index)} entries")




# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────
def main():
    print(f"\n{'='*60}")
    print(f"  Building: {SITE_NAME}")
    print(f"  Output:   {DIST_DIR}/")
    print(f"{'='*60}\n")

    # Clean _dist
    if DIST_DIR.exists():
        shutil.rmtree(DIST_DIR)
    DIST_DIR.mkdir()

    # Copy static assets first
    print("Copying static assets…")
    copy_assets()
    print()

    # Process HTML files
    print("Processing HTML pages…")
    ok = err = 0
    for src, dst in iter_source_files():
        rel = src.relative_to(BASE)
        try:
            process_file(src, dst)
            print(f"  ✓  {rel}  →  {dst.relative_to(DIST_DIR)}")
            ok += 1
        except Exception as e:
            print(f"  ✗  {rel}  ERROR: {e}")
            err += 1

    # robots.txt
    robots_src = BASE / 'robots.txt'
    if robots_src.exists():
        shutil.copy2(robots_src, DIST_DIR / 'robots.txt')
        print(f"\n  ✓  robots.txt copied")

    # Standalone pages (not processed through the theme pipeline)
    for standalone in ['calculator-widget.html']:
        src = BASE / standalone
        if src.exists():
            shutil.copy2(src, DIST_DIR / standalone)
            print(f"  ✓  {standalone} copied")

    # Copy sitemap files (synced from live WordPress site)
    for sitemap_file in ['sitemap.xml', 'sitemap-1.xml']:
        src = BASE / sitemap_file
        if src.exists():
            shutil.copy2(src, DIST_DIR / sitemap_file)
            print(f"\n  ✓  {sitemap_file} copied")

    # Generate search index
    generate_search_index()

    # Copy search.js
    search_js_src = THEME_DIR / 'search.js'
    if search_js_src.exists():
        search_js_dst = DIST_DIR / 'theme' / 'search.js'
        search_js_dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(search_js_src, search_js_dst)
        print(f"  ✓  theme/search.js copied")

    print(f"\n{'='*60}")
    print(f"  Done.  {ok} pages built, {err} errors.")
    print(f"  Deploy the _dist/ folder to any static host.")
    print(f"  To retheme: edit _theme/config.json, then re-run build.py")
    print(f"{'='*60}\n")


if __name__ == '__main__':
    main()
