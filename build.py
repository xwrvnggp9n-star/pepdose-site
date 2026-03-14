#!/usr/bin/env python3
"""
pep-dose.com — Content Prep Pipeline
======================================
Extracts article content from WordPress HTML exports, cleans it up,
and writes deploy-ready content files to _dist/.

USAGE:
    python3 build.py

OUTPUT:
    _dist/<slug>/index.html   (article body content only — no <head>, header, or footer)

deploy.py reads these files and pushes the content to WordPress.com via REST API.
WordPress handles all chrome (header, footer, nav, CSS) via its own template parts.
"""

import html as html_mod
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

# ─────────────────────────────────────────────────────────────────────────────
# Load config
# ─────────────────────────────────────────────────────────────────────────────
with open(CONFIG_FILE, encoding='utf-8') as f:
    C = json.load(f)

SITE_NAME  = C['site_name']
SITE_URL   = C.get('site_url', 'https://pep-dose.com')
COLORS     = C['colors']

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

# ─────────────────────────────────────────────────────────────────────────────
# HTML helpers
# ─────────────────────────────────────────────────────────────────────────────
def extract(pattern, text, group=1, flags=re.DOTALL):
    m = re.search(pattern, text, flags)
    return m.group(group) if m else ''

# ─────────────────────────────────────────────────────────────────────────────
# Content cleaning: strip PureLab references
# ─────────────────────────────────────────────────────────────────────────────
def strip_sponsor_sections(text):
    """Remove old PureLab references and external images. Keep WMP sponsor sections."""
    text = re.sub(
        r'<img[^>]*src="https?://purelabpeptides\.com/[^"]*"[^>]*/?>',
        '', text)
    text = re.sub(r'from Pure Lab Peptides[^"]*?(?=["<])', '', text)
    text = re.sub(r'by Pure Lab Peptides', '', text)
    text = re.sub(r'labeled[^"]*?Pure Lab Peptides', 'labeled', text)
    text = re.sub(r'A labeled vial of Pure Lab Peptides ', 'A labeled vial of ', text)
    text = re.sub(
        r'<li>[^<]*<strong>[^<]*</strong>[^<]*<a\s+href="https?://purelabpeptides\.com/[^"]*"[^>]*>[^<]*</a>[^<]*</li>\s*',
        '', text)
    text = re.sub(
        r'<div class="product-card">\s*<img[^>]*src="https?://purelabpeptides\.com/[^"]*"[^>]*/?>.*?</div>',
        '', text, flags=re.DOTALL)
    text = re.sub(
        r'<div class="product-card">\s*<img[^>]*>[^<]*<a\s+[^>]*href="https?://purelabpeptides\.com/[^"]*"[^>]*>[^<]*</a>\s*</div>',
        '', text, flags=re.DOTALL)
    text = re.sub(
        r'<div class="ref-line">\s*<i[^>]*></i><br\s*/?>\s*<strong>\s*Pure Lab Peptides\s*</strong>.*?</li>',
        '</li>', text, flags=re.DOTALL)
    text = re.sub(
        r'<a\s+[^>]*href="https?://purelabpeptides\.com/[^"]*"[^>]*>[^<]*</a>',
        '', text)
    text = re.sub(
        r'<a\s+href="https?://purelabpeptides\.com/[^"]*"[^>]*>([^<]*)</a>',
        r'\1', text)
    text = re.sub(r'https?://purelabpeptides\.com/[^\s"\'<>]*', '', text)
    text = re.sub(r',?"purelabpeptides\.com":"Pure Lab Peptides"', '', text)
    text = re.sub(r'\b(?:PureLabPeptides|Pure\s*Lab\s*Peptides)\b', '', text)
    text = re.sub(r'\(e\.g\.,\s*\)', '', text)
    text = re.sub(r'\(Available for reaseach\s*\)', '(Research compound)', text)
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
    return _SLUG_TO_NAME.get(slug, slug.replace('what-is-', '').replace('-vial-dosage-protocol', '').replace('-', ' ').title())


def sponsor_url_for_slug(slug):
    """Return the full WMP product URL with UTM tags for a given page slug."""
    product_path = SPONSOR_LINKS.get(slug, '')
    if product_path:
        base = SPONSOR_URL + product_path
    else:
        base = SPONSOR_URL
    utm = f'utm_source=pepdose&utm_medium=referral&utm_campaign=sponsor&utm_content={slug}'
    sep = '&' if '?' in base else '?'
    return base + sep + utm


def rewrite_existing_sponsor_links(html, sponsor_url):
    """Replace any existing WMP homepage links with the correct product URL + UTM tags."""
    html = re.sub(
        r'href="https?://whitemarketpeptides\.com/?(?:#[^"]*)?(?:\?[^"]*)?"',
        f'href="{sponsor_url}"',
        html)
    return html


def inject_inline_sponsor_link(html, product_url, peptide_name):
    """Insert a contextual sponsor paragraph before references or post-nav."""
    link = (
        f'<a href="{product_url}" rel="sponsored nofollow noopener" '
        f'target="_blank">{SPONSOR_NAME}</a>'
    )
    paragraph = (
        f'<p style="max-width:750px;font-family:inherit">Looking for research-grade {peptide_name}? '
        f'Our sponsor {link} carries {peptide_name} with third-party purity testing. '
        f'Use code <strong>{SPONSOR_CODE}</strong> for {SPONSOR_DEAL}.</p>'
    )
    # Try to insert before references, then post-nav, then append to end
    for marker in ['<section class="auto-references-section"',
                   '<div class="post-navigation"',
                   '<div class="post-navigation">']:
        if marker in html:
            return html.replace(marker, paragraph + '\n' + marker, 1)
    # Append to end of content
    return html + '\n' + paragraph


def inject_sponsor_cta(html, product_url, peptide_name):
    """Insert a styled CTA block before post navigation or at end of content."""
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
    # Try to insert before post-nav, then append to end
    for marker in ['<div class="post-navigation">',
                   '<div class="post-navigation"']:
        if marker in html:
            return html.replace(marker, cta + '\n' + marker, 1)
    # Append to end of content
    return html + '\n' + cta

# ─────────────────────────────────────────────────────────────────────────────
# Branding / author cleanup
# ─────────────────────────────────────────────────────────────────────────────
def sanitize_old_branding(text):
    """Replace old domain references that may linger in content or schema."""
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
    text = re.sub(
        r'<meta\s+name="author"\s+content="sec9vzion[^"]*"\s*/?>',
        '<meta name="author" content="Pep-Dose Staff" />',
        text,
    )
    return text

# ─────────────────────────────────────────────────────────────────────────────
# Lazy loading
# ─────────────────────────────────────────────────────────────────────────────
def add_lazy_loading(html):
    """Add loading='lazy' to images, except the first one (LCP candidate)."""
    img_count = [0]
    def lazy_replace(match):
        img_count[0] += 1
        tag = match.group(0)
        if img_count[0] == 1 or 'loading=' in tag:
            return tag
        if 'fetchpriority="high"' in tag:
            return tag
        return tag.replace('<img ', '<img loading="lazy" ')
    return re.sub(r'<img [^>]+/?>', lazy_replace, html)

# ─────────────────────────────────────────────────────────────────────────────
# Extract title from source HTML
# ─────────────────────────────────────────────────────────────────────────────
def extract_title(raw):
    """Extract the page title from <h1> or <title> in a WP export HTML file."""
    # Prefer <h1> — it's the visible heading
    h1 = extract(r'<h1[^>]*>(.*?)</h1>', raw)
    if h1:
        # Strip inner tags but keep text
        return re.sub(r'<[^>]+>', '', h1).strip()
    # Fallback to <title> tag, stripping site name suffix
    title = extract(r'<title[^>]*>(.*?)</title>', raw)
    if title:
        title = re.sub(r'\s*[\|–—]\s*(pep-dose\.com|PeptideDosages\.com).*', '', title)
        return html_mod.unescape(title).strip()
    return ''


# ─────────────────────────────────────────────────────────────────────────────
# Extract article content from a WP export HTML file
# ─────────────────────────────────────────────────────────────────────────────
def extract_article_content(raw):
    """Extract the article/main content from a full WP export HTML page.

    Returns the inner content of <article> or <main> — the part that WordPress
    stores as the post/page body. No <head>, header, footer, or nav included.
    """
    body_html = extract(r'<body[^>]*>(.*?)</body>', raw)

    # Try to get <main> content
    main_html = extract(r'(<main[^>]*>.*?</main>)', body_html)
    if not main_html:
        # Some WP exports omit </main>; grab from <main> to end of body
        main_html = extract(r'(<main[^>]*>.*)', body_html)
        if main_html:
            main_html += '</main>'
        else:
            return None

    # Strip old embedded footer and trailing junk from WP exports.
    main_html = re.sub(
        r'<footer class="site-footer"[^>]*>.*',
        '</main>', main_html, count=1, flags=re.DOTALL)
    # Strip old back-to-top buttons
    main_html = re.sub(
        r'<div class="back-to-top"[^>]*>.*?</div>',
        '', main_html, flags=re.DOTALL)
    # Strip old embedded <style> blocks for footer/dark-mode CSS
    main_html = re.sub(
        r'<style>\s*/\*[^<]*?(?:Footer|Dark Mode)[^<]*?\*/[^<]*?</style>',
        '', main_html, flags=re.DOTALL)
    # Strip ALL <script> blocks BEFORE looking for <article>
    # (prevents matching <article> inside JS template literals)
    main_html = re.sub(
        r'<script\b[^>]*>.*?</script>',
        '', main_html, flags=re.DOTALL)

    # Extract just the article content (strip the <main> wrapper)
    article = extract(r'<article[^>]*>(.*?)</article>', main_html)
    if article:
        return article.strip()

    # Fallback: content inside <main> tags
    inner = extract(r'<main[^>]*>(.*?)</main>', main_html)
    return inner.strip() if inner else main_html.strip()

# ─────────────────────────────────────────────────────────────────────────────
# Process a single HTML file
# ─────────────────────────────────────────────────────────────────────────────
def process_file(src_path, dst_path):
    with open(src_path, 'r', errors='replace') as f:
        raw = f.read()

    # ── Extract article content ──────────────────────────────────────────────
    content = extract_article_content(raw)
    if not content:
        return False

    # ── Extract and prepend title if missing ─────────────────────────────────
    # Many source files have <h1> outside <article>, so it's lost during extraction.
    if not re.search(r'<h1[\s>]', content):
        title = extract_title(raw)
        if title:
            content = f'<h1>{html_mod.escape(title)}</h1>\n{content}'

    # ── Apply content transformations ────────────────────────────────────────
    content = apply_colors(content)
    content = fix_urls(content)
    content = sanitize_old_branding(content)
    content = strip_sponsor_sections(content)

    # ── Update legal page dates to February 20, 2026 ─────────────────────────
    slug = src_path.parent.name if src_path.name == 'index.html' else src_path.stem
    if slug in ('disclaimer', 'privacy-policy', 'terms-conditions', 'cookie-policy'):
        content = re.sub(
            r'(?:Last updated|<strong>Last updated:</strong>)[^<]*(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}',
            '<strong>Last updated:</strong> February 20, 2026',
            content)

    # Inject/rewrite sponsor backlinks
    sponsor_url = sponsor_url_for_slug(slug)
    content = rewrite_existing_sponsor_links(content, sponsor_url)

    # Inject sponsor CTA + inline link for article and dosage protocol pages
    is_article = slug.startswith('what-is') or slug.startswith('what-are')
    is_dosage = 'dosage-protocol' in slug or 'vial-dosage' in slug
    is_educational = slug in ('combine-peptides-same-syringe', 'retatrutide-vs-tirzepatide',
                              'tesamorelin-reconstitution-storage')
    if is_article or is_dosage or is_educational:
        peptide_name = derive_peptide_name(slug)
        content = inject_inline_sponsor_link(content, sponsor_url, peptide_name)
        content = inject_sponsor_cta(content, sponsor_url, peptide_name)

    # Strip inline <style> from contact page (styles are in WP global CSS)
    if slug == 'contact-us':
        content = re.sub(r'<style>.*?</style>\s*', '', content, flags=re.DOTALL)

    content = add_lazy_loading(content)
    content = sanitize_author(content)

    # ── Write output ─────────────────────────────────────────────────────────
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    with open(dst_path, 'w', encoding='utf-8') as f:
        f.write(content)

    return True

# ─────────────────────────────────────────────────────────────────────────────
# Discover all source pages
# ─────────────────────────────────────────────────────────────────────────────
SKIP_DIRS = {'_dist', '_theme', 'wp-json', '.claude', '.git', '__pycache__',
             'wp-content', 'wp-includes', 'pepdose-favicon-plugin',
             '_dist 2', '_dist 3'}

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
                   and not d.startswith('index.html?')]

        if 'index.html' in files:
            src = root / 'index.html'
            dst = DIST_DIR / rel / 'index.html'
            yield src, dst

    # ── Bare HTML files ───────────────────────────────────────────────────────
    for name in BARE_HTML_FILES:
        src = BASE / name
        if src.exists():
            dst = DIST_DIR / name / 'index.html'
            yield src, dst


# ─────────────────────────────────────────────────────────────────────────────
# Static dosages catalog page (replaces JS-driven dynamic version)
# ─────────────────────────────────────────────────────────────────────────────
DOSAGE_CATEGORIES = {
    'single': {
        'label': 'Single Peptides',
        'parent_dir': 'single-peptide-dosages',
    },
    'blends': {
        'label': 'Peptide Blends',
        'parent_dir': 'peptide-blend-dosages',
    },
    'stacks': {
        'label': 'Peptide Stacks',
        'parent_dir': 'peptide-stack-dosages',
    },
}


def _protocol_display_name(dirname):
    """Convert a protocol directory name to a display-friendly title."""
    name = dirname.replace('-vial-dosage-protocol', '').replace('-dosage-protocol', '')
    # Handle known patterns: "bpc-157-5mg" → "BPC-157 — 5mg Vial"
    m = re.match(r'^(.+?)-(\d+(?:\.\d+)?m?g)$', name)
    if m:
        peptide = m.group(1).replace('-', ' ').title()
        dose = m.group(2)
        # Fix common peptide names
        peptide = re.sub(r'\bBpc\b', 'BPC', peptide)
        peptide = re.sub(r'\bGhk Cu\b', 'GHK-Cu', peptide)
        peptide = re.sub(r'\bTb 500\b', 'TB-500', peptide)
        peptide = re.sub(r'\bMots C\b', 'MOTS-c', peptide)
        peptide = re.sub(r'\bSema\b', 'Semaglutide', peptide)
        peptide = re.sub(r'\bGlow\b', 'GLOW', peptide)
        peptide = re.sub(r'\bKlow\b', 'KLOW', peptide)
        return f'{peptide} — {dose} Vial'
    # Fallback
    return name.replace('-', ' ').title()


def build_dosages_page():
    """Generate a static HTML catalog page for dosage protocols."""
    cards_by_cat = {}
    for cat_key, cat_info in DOSAGE_CATEGORIES.items():
        parent_dir = BASE / cat_info['parent_dir']
        entries = []
        if parent_dir.exists() and parent_dir.is_dir():
            for child in sorted(parent_dir.iterdir()):
                if child.is_dir() and (child / 'index.html').exists():
                    title = _protocol_display_name(child.name)
                    url = f'/{cat_info["parent_dir"]}/{child.name}/'
                    entries.append((title, url))
        cards_by_cat[cat_key] = entries

    # Build card HTML for each category
    all_cards = []
    for cat_key, cat_info in DOSAGE_CATEGORIES.items():
        entries = cards_by_cat[cat_key]
        if not entries:
            continue
        card_html = ''
        for title, url in entries:
            card_html += f'''<div style="background:#fff;border-radius:12px;box-shadow:0 2px 8px rgba(0,0,0,.08);overflow:hidden;transition:transform .2s,box-shadow .2s">
  <div style="padding:24px">
    <h3 style="margin:0 0 8px;font-size:1.1rem;color:#2e2a22">{html_mod.escape(title)}</h3>
    <p style="margin:0 0 16px;font-size:.9rem;color:#6b7280">Complete dosage protocol and reconstitution guide.</p>
    <a href="{url}" style="display:inline-block;padding:10px 20px;background:#c85a30;color:#fff;text-decoration:none;border-radius:6px;font-size:.9rem;font-weight:600">View Protocol &rarr;</a>
  </div>
</div>\n'''
        all_cards.append(f'''<h2 style="margin:2rem 0 1rem;color:#2e2a22">{cat_info['label']} ({len(entries)})</h2>
<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:20px;margin-bottom:2rem">
{card_html}</div>''')

    total = sum(len(v) for v in cards_by_cat.values())
    content = f'''<h1>Dosages &amp; Protocols</h1>
<p style="max-width:700px;margin:0 auto 2rem;text-align:center;color:#6b7280;font-size:1.05rem">
Browse our complete library of {total} peptide dosage protocols. Each protocol includes reconstitution
instructions, recommended dosing schedules, and syringe measurements.
</p>
{''.join(all_cards)}'''

    dst = DIST_DIR / 'dosages' / 'index.html'
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(content, encoding='utf-8')
    return True


# ─────────────────────────────────────────────────────────────────────────────
# Static blog/articles listing page
# ─────────────────────────────────────────────────────────────────────────────
# Slugs to exclude from the articles listing (non-article pages)
_BLOG_EXCLUDE = {'about-us', 'contact-us', 'cookie-policy', 'disclaimer',
                 'privacy-policy', 'terms-conditions', 'dosages', 'blog',
                 'home', 'peptide-dosage-calculator', 'category',
                 'peptide-stack-dosages', 'retatrutide'}
# Parent directories for dosage protocols (listed on dosages page, not articles)
_DOSAGE_PARENT_DIRS = {'single-peptide-dosages', 'peptide-blend-dosages',
                       'peptide-stack-dosages'}


def build_blog_page():
    """Generate a static articles listing page with ALL articles."""
    articles = []

    # Scan source directories for article pages
    for d in sorted(BASE.iterdir()):
        if not d.is_dir():
            continue
        slug = d.name
        if slug in _BLOG_EXCLUDE or slug in SKIP_DIRS:
            continue
        if slug in _DOSAGE_PARENT_DIRS:
            continue
        # Skip dosage protocol sub-pages and retatrutide dosage variants
        if 'dosage-protocol' in slug or re.match(r'retatrutide-\d+mg$', slug):
            continue
        src = d / 'index.html'
        if not src.exists():
            continue
        raw = src.read_text(errors='replace')
        title = extract_title(raw) or slug.replace('-', ' ').title()
        title = html_mod.unescape(title)
        # Determine URL — use WP slug (strip -2 suffix for display but keep for URL)
        url = f'/{slug}/'
        articles.append((title, url, slug))

    # Also pick up bare HTML educational articles
    for name in ['combine-peptides-same-syringe', 'retatrutide-vs-tirzepatide',
                 'tesamorelin-reconstitution-storage']:
        src = BASE / name
        if src.exists() and src.is_file():
            raw = src.read_text(errors='replace')
            title = extract_title(raw) or name.replace('-', ' ').title()
            title = html_mod.unescape(title)
            url = f'/{name}/'
            if (title, url, name) not in articles:
                articles.append((title, url, name))

    # Sort alphabetically by title
    articles.sort(key=lambda x: x[0].lower())

    # Build card HTML
    card_html = ''
    for title, url, slug in articles:
        card_html += f'''<div style="background:#fff;border-radius:12px;box-shadow:0 2px 8px rgba(0,0,0,.06);overflow:hidden;border:1px solid #e5e7eb">
  <div style="padding:20px 24px">
    <h3 style="margin:0 0 8px;font-size:1.05rem"><a href="{url}" style="color:#2e2a22;text-decoration:none">{html_mod.escape(title)}</a></h3>
    <a href="{url}" style="color:#c85a30;font-size:.9rem;font-weight:600;text-decoration:none">Read Article &rarr;</a>
  </div>
</div>\n'''

    content = f'''<h1>Education &amp; Articles</h1>
<p style="max-width:700px;margin:0 auto 2rem;text-align:center;color:#6b7280;font-size:1.05rem">
Explore our complete library of {len(articles)} peptide education articles. Each article provides
evidence-based information about mechanisms, benefits, dosing, and safety.
</p>
<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:16px;margin-bottom:2rem">
{card_html}</div>'''

    dst = DIST_DIR / 'blog' / 'index.html'
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(content, encoding='utf-8')
    return True


# ─────────────────────────────────────────────────────────────────────────────
# Calculator gateway page (WP strips <script>, so link to GitHub Pages)
# ─────────────────────────────────────────────────────────────────────────────
CALC_URL = 'https://xwrvnggp9n-star.github.io/pepdose-site/calculator-widget.html'


def build_calculator_page():
    """Generate a gateway page for the dosage calculator."""
    content = f'''<h1>Peptide Dosage Calculator</h1>
<p style="max-width:700px;margin:0 auto 1.5rem;text-align:center;color:#6b7280;font-size:1.05rem">
Enter your vial size, bacteriostatic water volume, and desired dose. The calculator
instantly shows your concentration, exact volumes to draw, and how many injections
you'll get from the vial.
</p>

<div style="text-align:center;margin:2rem 0">
<a href="{CALC_URL}" target="_blank" rel="noopener"
   style="display:inline-block;padding:16px 36px;background:#c85a30;color:#fff;text-decoration:none;border-radius:8px;font-size:1.15rem;font-weight:600;font-family:Poppins,sans-serif;box-shadow:0 4px 12px rgba(200,90,48,.3);transition:transform .2s">
  Open Calculator &rarr;
</a>
</div>

<div style="max-width:700px;margin:2rem auto;padding:24px;background:#fff;border-radius:12px;box-shadow:0 2px 8px rgba(0,0,0,.06)">
<h2 style="margin-top:0">How It Works</h2>
<ol style="line-height:1.8">
<li><strong>Choose your peptide</strong> — select from the list to auto-fill vial size and water volume, or enter values manually.</li>
<li><strong>Verify vial size &amp; water volume</strong> — auto-filled from the protocol but you can adjust if needed.</li>
<li><strong>Enter your desired dose</strong> — type the number and pick your unit (mcg, mg, or syringe units). Results update automatically.</li>
<li><strong>Read your results</strong> — concentration, all dose equivalents, and injections per vial appear instantly.</li>
</ol>

<h3>Understanding the Math</h3>
<p><strong>Concentration</strong> = Vial amount (mg) &divide; Water added (mL)</p>
<p><strong>Volume to draw</strong> = Dose (mg) &divide; Concentration (mg/mL)</p>
<p><strong>Syringe units</strong> = Volume (mL) &times; 100 &nbsp;(for a standard U-100 syringe)</p>
</div>

<p style="text-align:center;font-size:.85rem;color:#9ca3af;margin-top:2rem">
For educational and research purposes only. Always follow the guidance of a qualified healthcare professional.
</p>'''

    dst = DIST_DIR / 'peptide-dosage-calculator' / 'index.html'
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(content, encoding='utf-8')
    return True


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────
def main():
    print(f"\n{'='*60}")
    print(f"  Content Prep: {SITE_NAME}")
    print(f"  Output:       {DIST_DIR}/")
    print(f"{'='*60}\n")

    # Clean _dist
    if DIST_DIR.exists():
        shutil.rmtree(DIST_DIR)
    DIST_DIR.mkdir()

    # Pages that are generated statically (skip the source HTML extraction)
    GENERATED_SLUGS = {'dosages', 'peptide-dosage-calculator', 'blog'}

    # Process HTML files
    print("Extracting and cleaning article content…")
    ok = err = 0
    for src, dst in iter_source_files():
        rel = src.relative_to(BASE)
        slug = src.parent.name if src.name == 'index.html' else src.stem
        if slug in GENERATED_SLUGS:
            continue  # handled separately below
        try:
            if process_file(src, dst):
                print(f"  ✓  {rel}")
                ok += 1
            else:
                print(f"  ⚠  {rel}  (no article content found, skipped)")
        except Exception as e:
            print(f"  ✗  {rel}  ERROR: {e}")
            err += 1

    # Generate static dosages catalog page
    if build_dosages_page():
        print(f"  ✓  dosages/index.html (generated static catalog)")
        ok += 1

    # Generate blog/articles listing page
    if build_blog_page():
        print(f"  ✓  blog/index.html (generated articles listing)")
        ok += 1

    # Generate calculator gateway page
    if build_calculator_page():
        print(f"  ✓  peptide-dosage-calculator/index.html (generated gateway)")
        ok += 1

    # Copy standalone files that bypass the pipeline
    for standalone in ['calculator-widget.html']:
        src = BASE / standalone
        if src.exists():
            shutil.copy2(src, DIST_DIR / standalone)
            print(f"\n  ✓  {standalone} copied (standalone)")

    # robots.txt
    robots_src = BASE / 'robots.txt'
    if robots_src.exists():
        shutil.copy2(robots_src, DIST_DIR / 'robots.txt')
        print(f"  ✓  robots.txt copied")

    # Sitemap files
    for sitemap_file in ['sitemap.xml', 'sitemap-1.xml']:
        src = BASE / sitemap_file
        if src.exists():
            shutil.copy2(src, DIST_DIR / sitemap_file)
            print(f"  ✓  {sitemap_file} copied")

    print(f"\n{'='*60}")
    print(f"  Done.  {ok} pages prepped, {err} errors.")
    print(f"  Next:  python3 deploy.py          (deploy all)")
    print(f"         python3 deploy.py --dry-run (preview)")
    print(f"{'='*60}\n")


if __name__ == '__main__':
    main()
