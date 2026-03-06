#!/usr/bin/env python3
"""
Peptide Dosages — Static Site Builder
======================================
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
LOGO       = C['logo']
FAVICONS   = C['favicon']
FONTS      = C['fonts']
COLORS     = C['colors']
NAV_ITEMS  = C.get('nav', [])
FOOTER_CFG = C.get('footer', {})

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
def build_head(title, meta_desc, canonical, og_image, schema, custom_css_text):
    font_link = f'<link href="{FONTS["google_url"]}" rel="stylesheet"/>' if FONTS.get('google_url') else ''
    custom_css_block = f'\n    <style id="wp-custom-css">{custom_css_text}</style>' if custom_css_text.strip() else ''
    canon_tag = f'\n    <link rel="canonical" href="{fix_urls(canonical)}" />' if canonical else ''
    og_tag = f'\n    <meta property="og:image" content="{fix_urls(og_image)}" />' if og_image else ''

    return f'''\
<!DOCTYPE html>
<html lang="en-US">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{title}</title>
    <meta name="description" content="{meta_desc}" />{canon_tag}
    <meta property="og:type" content="website" />
    <meta property="og:title" content="{title}" />
    <meta property="og:description" content="{meta_desc}" />{og_tag}
    {fix_urls(schema)}
    <link rel="icon" href="{FAVICONS['32x32']}" sizes="32x32" />
    <link rel="icon" href="{FAVICONS['192x192']}" sizes="192x192" />
    <link rel="apple-touch-icon" href="{FAVICONS['apple_touch']}" />
    <meta name="msapplication-TileImage" content="{FAVICONS['mstile']}" />
    {font_link}
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css"/>
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
      <img src="{logo_url}" alt="{logo_alt}">
      <div class="header-logo-text">
        <span class="peptide">{span1}</span>
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
          <input type="search" class="header-search-input" placeholder="Search protocols..." name="s" required>
          <button type="submit" class="header-search-btn">
            <i class="fas fa-search"></i><span>Search</span>
          </button>
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
    quick_links   = build_footer_links(FOOTER_CFG.get('quick_links', []))
    resource_links = build_footer_links(FOOTER_CFG.get('resource_links', []))
    social        = FOOTER_CFG.get('social', {})
    about_text    = FOOTER_CFG.get('about_text', '')
    disclaimer    = FOOTER_CFG.get('disclaimer', '')
    copyright_name = FOOTER_CFG.get('copyright', SITE_NAME)
    logo_url      = LOGO['img_url']
    span1         = LOGO['span_1']
    span2         = LOGO['span_2']

    def social_link(platform, icon):
        url = social.get(platform, '#')
        return f'<a href="{url}" class="social-link" aria-label="{platform.title()}"><i class="fab fa-{icon}"></i></a>'

    return f'''\
<footer class="site-footer" role="contentinfo">
  <div class="footer-wave"></div>
  <div class="footer-main">
    <div class="footer-container">
      <div class="footer-grid">

        <div class="footer-column footer-about">
          <div class="footer-logo">
            <img src="{logo_url}" alt="{SITE_NAME}">
            <span><span class="peptide">{span1}</span><span class="dosages">{span2}</span></span>
          </div>
          <p>{about_text}</p>
          <div class="footer-social">
            {social_link('facebook', 'facebook-f')}
            {social_link('twitter', 'twitter')}
            {social_link('linkedin', 'linkedin-in')}
            {social_link('youtube', 'youtube')}
          </div>
        </div>

        <div class="footer-column">
          <h3>Quick Links</h3>
          <ul class="footer-links">
{quick_links}
          </ul>
        </div>

        <div class="footer-column">
          <h3>Resources</h3>
          <ul class="footer-links">
{resource_links}
          </ul>
        </div>

        <div class="footer-column">
          <div class="footer-newsletter">
            <h3>Stay Updated</h3>
            <p style="color:#bdc3c7;margin-bottom:15px;">Get the latest peptide research and protocols delivered to your inbox.</p>
            <form class="newsletter-form" onsubmit="return false;">
              <input type="email" placeholder="Your email" required>
              <button type="submit">Subscribe</button>
            </form>
          </div>
        </div>

      </div>

      <div class="footer-disclaimer">
        <p><strong>Important Disclaimer:</strong> {disclaimer}</p>
      </div>
    </div>
  </div>

  <div class="footer-bottom">
    <div class="footer-container">
      <div class="footer-bottom-content">
        <div class="footer-copyright">
          &copy; <span id="currentYear"></span> {copyright_name}. All rights reserved.
        </div>
        <ul class="footer-legal-links">
          <li><a href="/privacy-policy">Privacy Policy</a></li>
          <li><a href="/terms-conditions">Terms &amp; Conditions</a></li>
          <li><a href="/cookie-policy">Cookie Policy</a></li>
          <li><a href="/disclaimer">Disclaimer</a></li>
        </ul>
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

</body>
</html>'''

# ─────────────────────────────────────────────────────────────────────────────
# Process a single HTML file
# ─────────────────────────────────────────────────────────────────────────────
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

    # Page-specific custom CSS (from wp-custom-css block)
    custom_css = extract(r'<style[^>]*id="wp-custom-css"[^>]*>(.*?)</style>', head_html)

    # ── Extract body ──────────────────────────────────────────────────────────
    body_html = extract(r'<body[^>]*>(.*?)</body>', raw)

    # Get the <main> block (contains all page-specific content + inline CSS)
    main_html = extract(r'(<main[^>]*>.*?</main>)', body_html)
    if not main_html:
        main_html = '<main id="main-content"><p>Content unavailable.</p></main>'

    # ── Apply transformations ─────────────────────────────────────────────────
    main_html  = apply_colors(main_html)
    main_html  = fix_urls(main_html)
    main_html  = fix_logo_urls(main_html)
    custom_css = apply_colors(custom_css)

    # ── Assemble page ─────────────────────────────────────────────────────────
    head_section = build_head(title, meta_desc, canonical, og_image, schema, custom_css)
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
    'single-peptide-dosages', 'peptide-stack-dosages',
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

    print(f"\n{'='*60}")
    print(f"  Done.  {ok} pages built, {err} errors.")
    print(f"  Deploy the _dist/ folder to any static host.")
    print(f"  To retheme: edit _theme/config.json, then re-run build.py")
    print(f"{'='*60}\n")


if __name__ == '__main__':
    main()
