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
    """Insert a contextual sponsor paragraph before the references section."""
    link = (
        f'<a href="{product_url}" rel="sponsored nofollow noopener" '
        f'target="_blank">{SPONSOR_NAME}</a>'
    )
    paragraph = (
        f'<p style="max-width:750px;font-family:inherit">Looking for research-grade {peptide_name}? '
        f'Our sponsor {link} carries {peptide_name} with third-party purity testing. '
        f'Use code <strong>{SPONSOR_CODE}</strong> for {SPONSOR_DEAL}.</p>'
    )
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
    marker = '<div class="post-navigation">'
    if marker not in html:
        marker = '<div class="post-navigation"'
    if marker in html:
        html = html.replace(marker, cta + '\n' + marker, 1)
    elif '</article>' in html:
        html = html.replace('</article>', cta + '\n</article>', 1)
    return html

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
    # Strip old <script> blocks between </article> and what was the footer
    main_html = re.sub(
        r'(</article>\s*</div>)\s*(?:<!--[^>]*-->\s*)*(?:<script\b[^>]*>.*?</script>\s*)*',
        r'\1\n', main_html, flags=re.DOTALL)

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

    # ── Apply content transformations ────────────────────────────────────────
    content = apply_colors(content)
    content = fix_urls(content)
    content = sanitize_old_branding(content)
    content = strip_sponsor_sections(content)

    # Inject/rewrite sponsor backlinks for pages with matching WMP products
    slug = src_path.parent.name if src_path.name == 'index.html' else src_path.stem
    sponsor_url = sponsor_url_for_slug(slug)
    content = rewrite_existing_sponsor_links(content, sponsor_url)

    product_path = SPONSOR_LINKS.get(slug)
    if product_path and slug.startswith('what-is'):
        peptide_name = derive_peptide_name(slug)
        content = inject_inline_sponsor_link(content, sponsor_url, peptide_name)
        content = inject_sponsor_cta(content, sponsor_url, peptide_name)

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

    # Process HTML files
    print("Extracting and cleaning article content…")
    ok = err = 0
    for src, dst in iter_source_files():
        rel = src.relative_to(BASE)
        try:
            if process_file(src, dst):
                print(f"  ✓  {rel}")
                ok += 1
            else:
                print(f"  ⚠  {rel}  (no article content found, skipped)")
        except Exception as e:
            print(f"  ✗  {rel}  ERROR: {e}")
            err += 1

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
