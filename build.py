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
CONFIG_FILE  = THEME_DIR / 'config.json'
CONTENT_FILE = THEME_DIR / 'content.json'

# ─────────────────────────────────────────────────────────────────────────────
# Load config + content
# ─────────────────────────────────────────────────────────────────────────────
with open(CONFIG_FILE, encoding='utf-8') as f:
    C = json.load(f)
with open(CONTENT_FILE, encoding='utf-8') as f:
    CONTENT = json.load(f)

SITE_NAME  = C['site_name']
SITE_URL   = C.get('site_url', 'https://pep-dose.com')

# ─────────────────────────────────────────────────────────────────────────────
# Color replacement: old hardcoded hex → new theme hex
# Add entries to _theme/config.json → "color_replacements" as needed.
# ─────────────────────────────────────────────────────────────────────────────
_COLOR_REPLACEMENTS = C.get('color_replacements', {})

def apply_colors(text):
    """Replace old hardcoded inline colors with current theme colors."""
    for old, new in _COLOR_REPLACEMENTS.items():
        text = text.replace(old, new).replace(old.upper(), new)
    return text

# ─────────────────────────────────────────────────────────────────────────────
# URL helpers
# ─────────────────────────────────────────────────────────────────────────────
DOMAIN = 'https://pep-dose.com'

def fix_urls(text):
    """Make internal absolute URLs relative, and fix known -2 suffix slugs."""
    text = text.replace(DOMAIN + '/', '/').replace(DOMAIN, '/')
    # Fix -2 suffix slugs that exist in source HTML bodies but don't match live WP URLs
    for dir_slug, live_slug in _DIR_TO_LIVE_SLUG.items():
        text = text.replace(f'/{dir_slug}/', f'/{live_slug}/')
    # Fix GHK-Cu 100mg URL typo in some source files (100-mg vs 100mg)
    text = text.replace('ghk-cu-100-mg-vial-dosage-protocol', 'ghk-cu-100mg-vial-dosage-protocol')
    return text


# Paths that don't exist on the live site — links to these are stripped.
# Add entries here whenever a source article references a page not yet created.
_BROKEN_INTERNAL_PATHS = {
    '/single-peptide-dosages/ipamorelin-5mg-vial-dosage-protocol/',
    '/single-peptide-dosages/ipamorelin-10mg-vial-dosage-protocol/',
    '/single-peptide-dosages/5-amino-1mq-10-mg-vial-dosage-protocol/',
    '/single-peptide-dosages/mazdutide-5mg-vial-dosage-protocol/',
    '/single-peptide-dosages/mazdutide-10mg-vial-dosage-protocol/',
    '/single-peptide-dosages/ovagen-20mg-vial-dosage-protocol/',
    '/single-peptide-dosages/pnc-27-30-mg-vial-dosage-protocol/',
    '/single-peptide-dosages/prostamax-20mg-vial-dosage-protocol/',
    '/single-peptide-dosages/selank-5mg-vial-dosage-protocol/',
    '/single-peptide-dosages/selank-10mg-vial-dosage-protocol/',
    '/single-peptide-dosages/tesamorelin-20mg-vial-dosage-protocol/',
    '/single-peptide-dosages/vesugen-20mg-vial-dosage-protocol/',
    '/single-peptide-dosages/kpv-5mg-vial-dosage-protocol/',
    '/single-peptide-dosages/tirzepatide-5mg-vial-dosage-protocol/',
    '/single-peptide-dosages/tirzepatide-15mg-vial-dosage-protocol/',
    '/single-peptide-dosages/vilon-20mg-vial-dosage-protocol/',
}

def strip_broken_links(text):
    """Strip <a> tags whose href points to a known-404 internal path.
    Keeps the anchor text so surrounding sentences still read naturally."""
    for path in _BROKEN_INTERNAL_PATHS:
        # Remove the anchor tag but keep its text content
        text = re.sub(
            r'<a\s+[^>]*href=["\']' + re.escape(path) + r'["\'][^>]*>(.*?)</a>',
            r'\1', text, flags=re.DOTALL)
    return text

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

_SLUG_TO_NAME = CONTENT.get('slug_names', {})


# Shared title-case corrections applied after .title() — used by both
# derive_peptide_name() and _protocol_display_name().
_PEPTIDE_NAME_FIXES = [
    (r'\bBpc 157\b',        'BPC-157'),
    (r'\bGhk Cu\b',         'GHK-Cu'),
    (r'\bTb 500\b',         'TB-500'),
    (r'\bMots C\b',         'MOTS-c'),
    (r'\bSema\b',           'Semaglutide'),
    (r'\bGlow\b',           'GLOW'),
    (r'\bKlow\b',           'KLOW'),
    (r'\bDsip\b',           'DSIP'),
    (r'\bWolverine Stack\b','Wolverine Stack'),
    (r'\bRetatrutide\b',    'Retatrutide'),
    (r'(\d+)\s*Mg\b',       r'\1 mg'),    # "100Mg" → "100 mg"
]


def _fix_peptide_name_case(name):
    """Apply standard title-case corrections for known peptide names."""
    for pattern, replacement in _PEPTIDE_NAME_FIXES:
        name = re.sub(pattern, replacement, name)
    return name


def derive_peptide_name(slug):
    """Convert a page slug like 'what-is-bpc-157' to a display name."""
    if slug in _SLUG_TO_NAME:
        return _SLUG_TO_NAME[slug]
    # Strip common prefixes/suffixes to get the raw peptide part
    name = slug.replace('what-is-', '')
    for suffix in ('-vial-dosage-protocol', '-dosage-protocol'):
        name = name.replace(suffix, '')
    return _fix_peptide_name_case(name.replace('-', ' ').title())


def sponsor_url_for_slug(slug):
    """Return the full WMP product URL with UTM tags for a given page slug."""
    product_path = SPONSOR_LINKS.get(slug, '')
    if product_path:
        base = SPONSOR_URL + product_path
    else:
        base = SPONSOR_URL
    utm = f'utm_source=pep-dose&utm_medium=referral&utm_campaign=sponsor&utm_content={slug}'
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


# ─────────────────────────────────────────────────────────────────────────────
# Source dir name → live WP slug (for dirs with -2 suffix that WP doesn't use)
# Single source of truth: _theme/config.json → "slug_aliases"
# ─────────────────────────────────────────────────────────────────────────────
_DIR_TO_LIVE_SLUG = C.get('slug_aliases', {})

# ─────────────────────────────────────────────────────────────────────────────
# Related Reading cross-links + article images — loaded from content.json
# ─────────────────────────────────────────────────────────────────────────────
# Convert JSON [{url, title}] format → [(url, title)] tuples used internally
def _links(data):
    return [(d['url'], d['title']) for d in data]

_DOSAGE_RELATED  = {k: _links(v) for k, v in CONTENT.get('dosage_related', {}).items()}
_ARTICLE_RELATED = {k: _links(v) for k, v in CONTENT.get('article_related', {}).items()}
_ARTICLE_WMP_IMAGES = {
    k: (v['image'], v['wmp_url'])
    for k, v in CONTENT.get('article_wmp_images', {}).items()
}
_WMP_CDN  = 'https://i0.wp.com/whitemarketpeptides.com/wp-content/uploads/2026/02/'
_WMP_BASE = 'https://whitemarketpeptides.com'


def clean_headers(content):
    """Remove AI-generated jargon from article section headers."""
    # Patterns to strip from h2/h3 tags:
    # 1. Parenthetical qualifiers at end: (40–60 words), (educational), (NLP-friendly), etc.
    # 2. "Fast Answer / Executive Summary" → "The Short Answer"
    # 3. "Entity Properties" h3 → remove entirely
    # 4. "Core Concepts & Key Entities" → "Key Concepts"
    # 5. "Templates / Checklist / Example" → "Quick Reference Checklist"
    # 6. Trailing qualifiers like "answer-first", "snippet-optimized", "copy-ready"

    # Remove entire h3s that are just "Entity Properties" labels
    content = re.sub(
        r'<h3>[^<]*Entity Properties[^<]*</h3>\s*',
        '', content)

    # Remove entire h3s that are "Copy-ready Checklist" or "Snapshot Table" junk
    content = re.sub(
        r'<h3>[^<]*(?:Copy[‑\-]ready Checklist|Snapshot Table)[^<]*</h3>\s*',
        '', content)

    # Normalize "Fast Answer / Executive Summary" headers
    content = re.sub(
        r'<(h[23])>[^<]*(?:Fast Answer|Executive Summary)[^<]*</\1>',
        r'<\1>The Short Answer</\1>', content)

    # Normalize "Core Concepts & Key Entities" or similar
    content = re.sub(
        r'<(h[23])>[^<]*Core Concepts[^<]*</\1>',
        r'<\1>Key Concepts</\1>', content)

    # "Templates / Checklist / Example" → "Quick Reference"
    content = re.sub(
        r'<(h[23])>[^<]*Templates\s*/\s*Checklist[^<]*</\1>',
        r'<\1>Quick Reference</\1>', content)

    # "Step-by-Step / How-To (Educational...)" → "How to Use" (preserve meaningful titles)
    content = re.sub(
        r'<(h[23])>Step[‑\-]by[‑\-]Step\s*/\s*How[‑\-]To[^<]*</\1>',
        r'<\1>How to Use</\1>', content)
    content = re.sub(
        r'<(h[23])>Step[‑\-]by[‑\-]Step[^<]*\(Educational[^)]*\)[^<]*</\1>',
        r'<\1>How to Use</\1>', content)

    # Strip trailing parenthetical qualifiers from all h2/h3
    # e.g. "FAQs (NLP-friendly; 40–80 words each)" → "Frequently Asked Questions"
    # First handle FAQ variants
    content = re.sub(
        r'<(h[23])>\s*FAQs?\s*\([^)]*\)\s*</\1>',
        r'<\1>Frequently Asked Questions</\1>', content)

    # Strip remaining parentheticals: "Comparison / Alternatives (foo vs. bar)" → "Comparison"
    content = re.sub(
        r'(<h[23]>[^<]+?)\s*\([^)]{5,}\)(</h[23]>)',
        r'\1\2', content)

    # Strip em-dash separated qualifiers: "Comparison — Ipamorelin vs. GHRP-2" keep as-is
    # but remove qualifiers like "(with parenthetical)", "(Information Gain)" that sneak through
    content = re.sub(
        r'(<h[23]>[^<]+?)\s*\((?:with parenthetical|Information Gain|Answer[‑\-]First|PAA[‑\-]style|copy[‑\-]ready|snippet[‑\-]optimized)[^)]*\)(</h[23]>)',
        r'\1\2', content)

    return content


def inject_article_image(content, slug):
    """Add a floated WMP product image after the first paragraph if article has a WMP product
    but no existing product image in the content."""
    # Source dirs may have -2 suffix (e.g. what-is-ghk-cu-2 → what-is-ghk-cu)
    lookup_slug = re.sub(r'-2$', '', slug)
    if lookup_slug not in _ARTICLE_WMP_IMAGES:
        return content
    # Skip if article already has a WMP product image
    if 'whitemarketpeptides.com/wp-content/uploads' in content:
        return content
    img_file, product_path = _ARTICLE_WMP_IMAGES[lookup_slug]
    cdn_url = f'{_WMP_CDN}{img_file}?fit=300%2C300&ssl=1'
    product_url = f'{_WMP_BASE}{product_path}?utm_source=pep-dose&utm_medium=article&utm_campaign=wmp'
    img_html = (
        f'<div style="float:right;margin:0 0 1rem 1.5rem;max-width:160px;border-radius:8px;overflow:hidden">'
        f'<a href="{product_url}" target="_blank" rel="noopener">'
        f'<img src="{cdn_url}" alt="White Market Peptides product" '
        f'width="160" height="160" loading="lazy" style="display:block;width:100%;height:auto">'
        f'</a></div>'
    )
    # Insert after the first closing </p> tag
    return content.replace('</p>', f'</p>\n{img_html}', 1)


def strip_hero_image(content):
    """Remove broken featured-image divs (old WP export media not present on the live site)."""
    # Remove <div class="featured-image">...<img .../></div>
    content = re.sub(
        r'<div class="featured-image">\s*<img[^>]*/?>[\s\S]*?</div>\s*',
        '', content)
    # Catch any remaining standalone wp-post-image tags
    content = re.sub(
        r'<img[^>]*class="[^"]*wp-post-image[^"]*"[^>]*/?>[\s\n]*',
        '', content)
    return content


def wrap_tables(content):
    """Wrap bare <table> elements in a responsive overflow container with basic styling."""
    def _wrap(m):
        # Skip tables already inside a responsive wrapper
        context = content[max(0, m.start() - 150): m.start()]
        if 'table-responsive' in context or 'overflow-x' in context:
            return m.group(0)
        inner = m.group(0)
        inner = inner.replace(
            '<table>',
            '<table style="width:100%;border-collapse:collapse;font-size:.88rem;line-height:1.5">',
            1)
        inner = re.sub(
            r'<th([^>]*)>',
            r'<th\1 style="padding:.5rem .75rem;background:#2e2a22;color:#fdf8f0;'
            r'text-align:left;font-weight:600;white-space:nowrap;border:1px solid #c8bfb0">',
            inner)
        inner = re.sub(
            r'<td([^>]*)>',
            r'<td\1 style="padding:.5rem .75rem;border:1px solid #e5e0d5;vertical-align:top">',
            inner)
        return ('<div style="overflow-x:auto;-webkit-overflow-scrolling:touch;margin:1.5rem 0">'
                + inner + '</div>')
    return re.sub(r'<table>[\s\S]*?</table>', _wrap, content)


def _get_related_links(slug, is_dosage):
    """Return list of (url, title) related reading links for a page slug."""
    if is_dosage:
        for key in _DOSAGE_RELATED:
            if key in slug:
                return _DOSAGE_RELATED[key]
        return []
    else:
        return _ARTICLE_RELATED.get(slug, [])


def inject_related_reading(html, slug, is_dosage):
    """Insert a 'Related Reading' section with cross-links and calculator recommendation."""
    links = _get_related_links(slug, is_dosage)
    if not links:
        return html

    items = ''.join(
        f'<li><a href="{url}" style="color:#c85a30;text-decoration:none;font-weight:600">{title}</a></li>\n'
        for url, title in links
    )
    # Always add calculator link
    items += '<li><a href="/peptide-dosage-calculator/" style="color:#c85a30;text-decoration:none;font-weight:600">Peptide Dosage Calculator</a></li>\n'

    subtitle = 'Learn more about the peptides in this protocol:' if is_dosage else 'Continue reading about related topics:'
    section = f'''<section id="related-reading" class="section-block fade-in delay-3" style="background:#faf5ec;border:1px solid #e5e0d5;border-radius:12px;padding:1.5rem 2rem;margin:2rem 0;">
<h2 style="margin-top:0;font-size:1.25rem;color:#2e2a22"><i class="fas fa-book-reader"></i> Related Reading</h2>
<p style="color:#6b7280;margin-bottom:1rem">{subtitle}</p>
<ul style="list-style:none;padding:0;margin:0;display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:8px 24px">
{items}</ul>
</section>'''

    # Insert before the sponsored partner section, important-note, or references
    for marker in ['<section id="important-note"',
                   '<section class="references-section"']:
        if marker in html:
            return html.replace(marker, section + '\n' + marker, 1)
    # Fallback: append before sponsor injection point
    return html + '\n' + section


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
# Structured data (Schema.org Microdata)
# ─────────────────────────────────────────────────────────────────────────────
# WP.com strips <script> tags, so we use Microdata (HTML attributes) instead
# of JSON-LD.  Google supports both formats equally.

def inject_faq_schema(html):
    """Wrap FAQ sections in FAQPage microdata for rich snippet eligibility.

    Detects the pattern:  <strong>Q\\d+: question?</strong><br/> answer...
    and wraps each Q/A pair in schema.org/Question + Answer microdata.
    """
    # Find the FAQ heading (use [^<]* instead of .*? to avoid spanning across tags)
    faq_match = re.search(
        r'(<h2[^>]*>[^<]*FAQ[^<]*</h2>)',
        html, re.IGNORECASE
    )
    if not faq_match:
        return html

    faq_start = faq_match.end()

    # Find the end of the FAQ section (next <h2> or section-ending marker)
    next_section = re.search(
        r'<h2[\s>]|<section[\s>]|<div class="post-navigation|<div class="sponsor-cta',
        html[faq_start:]
    )
    faq_end = faq_start + next_section.start() if next_section else len(html)
    faq_block = html[faq_start:faq_end]

    # Parse individual Q&A pairs, supporting multiple formats:
    #   Format A: <p><strong>Q1: question?</strong><br/> answer</p>
    #   Format B: <p><strong>1) question?</strong><br/> answer</p>
    #   Format C: <h3>question?</h3><p>answer</p>
    #   Format D: <p><strong>Question?</strong> answer...</p>  (bold question inline)
    qa_pairs = []

    # Try Format A/B first: numbered Q&A inside <p> tags
    # Matches: Q1: question, 1) question, Q: question (with or without number)
    qa_pattern_ab = re.compile(
        r'<p>\s*<strong>\s*(?:Q\d*[:\)]\s*|\d+[:\)]\s*)(.+?)\??\s*</strong>'
        r'\s*(?:<br\s*/?>)?\s*'
        r'(.*?)</p>',
        re.DOTALL
    )
    qa_pairs = qa_pattern_ab.findall(faq_block)

    # Try Format C: <h3>question?</h3> followed by <p>answer</p>
    if not qa_pairs:
        qa_pattern_c = re.compile(
            r'<h3>(.+?\??)</h3>\s*<p>(.*?)</p>',
            re.DOTALL
        )
        qa_pairs = qa_pattern_c.findall(faq_block)

    # Try Format D: <p><strong>Question?</strong> answer text...</p>
    if not qa_pairs:
        qa_pattern_d = re.compile(
            r'<p>\s*<strong>([^<]*?\?)</strong>\s*'
            r'(.*?)</p>',
            re.DOTALL
        )
        qa_pairs = qa_pattern_d.findall(faq_block)

    if not qa_pairs:
        return html

    # Build microdata-enhanced FAQ block
    new_faq = '<div itemscope itemtype="https://schema.org/FAQPage">\n'
    new_faq += faq_match.group(0) + '\n'  # keep the <h2>FAQ</h2> heading

    for question, answer in qa_pairs:
        # Clean up question text (strip inner HTML tags for the itemprop name)
        q_clean = re.sub(r'<[^>]+>', '', question).strip().rstrip('?') + '?'
        # Keep the answer HTML as-is for display, but also provide a plain-text version
        a_text = re.sub(r'<[^>]+>', '', answer).strip()
        new_faq += (
            '<div itemscope itemprop="mainEntity" itemtype="https://schema.org/Question">\n'
            f'<p><strong itemprop="name">{q_clean}</strong><br />\n'
            f'<span itemscope itemprop="acceptedAnswer" itemtype="https://schema.org/Answer">'
            f'<span itemprop="text">{answer.strip()}</span></span></p>\n'
            '</div>\n'
        )

    new_faq += '</div>'

    # Replace the original FAQ heading + Q&A block with the microdata version
    return html[:faq_match.start()] + new_faq + html[faq_end:]


def inject_howto_schema(html, slug):
    """Wrap dosage protocol pages in HowTo microdata for rich snippet eligibility.

    Targets the reconstitution steps (<ol>) and wraps the page content with
    schema.org/HowTo markup.
    """
    # Extract the page title for the HowTo name
    title_match = re.search(r'<h1[^>]*>(.*?)</h1>', html)
    if not title_match:
        return html
    title = re.sub(r'<[^>]+>', '', title_match.group(1)).strip()

    # Extract the intro description (first <p> in intro-card or first <p> overall)
    desc_match = re.search(
        r'<div[^>]*class="intro-content"[^>]*>.*?<p>(.*?)</p>',
        html, re.DOTALL
    )
    if not desc_match:
        desc_match = re.search(r'<p>(.*?)</p>', html, re.DOTALL)
    description = ''
    if desc_match:
        description = re.sub(r'<[^>]+>', '', desc_match.group(1)).strip()[:200]

    # Find the reconstitution steps <ol>
    ol_match = re.search(r'<h3>(?:Reconstitution Steps|How to Reconstitute)</h3>\s*(<ol>.*?</ol>)', html, re.DOTALL)
    if not ol_match:
        return html

    ol_html = ol_match.group(1)
    # Parse <li> items
    steps = re.findall(r'<li>(.*?)</li>', ol_html, re.DOTALL)
    if not steps:
        return html

    # Build microdata-enhanced <ol>
    new_ol = '<ol>\n'
    for i, step_text in enumerate(steps, 1):
        step_clean = step_text.strip()
        new_ol += (
            f'<li itemprop="step" itemscope itemtype="https://schema.org/HowToStep">'
            f'<meta itemprop="position" content="{i}" />'
            f'<span itemprop="text">{step_clean}</span>'
            f'</li>\n'
        )
    new_ol += '</ol>'

    # Replace original <ol> with microdata version
    html = html.replace(ol_html, new_ol)

    # Wrap the entire content in a HowTo itemscope
    # Add the wrapper right after <h1>
    howto_meta = (
        f'<div itemscope itemtype="https://schema.org/HowTo">'
        f'<meta itemprop="name" content="{html_mod.escape(title)}" />'
        f'<meta itemprop="description" content="{html_mod.escape(description)}" />\n'
    )
    # Insert after <h1> tag
    html = re.sub(
        r'(</h1>)',
        r'\1\n' + howto_meta,
        html, count=1
    )
    # Close the div before the sponsor CTA or at the end
    for marker in ['<div class="sponsor-cta">',
                   '<section id="important-note"',
                   '<section class="references-section"']:
        if marker in html:
            html = html.replace(marker, '</div>\n' + marker, 1)
            break
    else:
        html += '\n</div>'

    return html


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
# Page heading: split H1 into headline + subhead, reduce size
# ─────────────────────────────────────────────────────────────────────────────
def rewrite_page_heading(content, slug):
    """Replace the page H1 with a smaller headline + optional subhead.

    Protocol pages: "BPC-157 (10 mg Vial) Dosage Protocol"
        → h1: "BPC-157 (10 mg)"  subhead: "Dosage Protocol"
    Article pages:  "What Is X? The Full Subtitle"
        → h1: "What Is X?"       subhead: "The Full Subtitle"
    """
    m = re.match(r'(<h1[^>]*>)(.*?)(</h1>)', content, re.DOTALL)
    if not m:
        return content

    title    = m.group(2)
    headline = title
    subhead  = None

    if 'dosage-protocol' in slug or 'vial-dosage' in slug:
        dp = re.match(r'^(.+?)\s+Dosage Protocol\b.*$', title, re.IGNORECASE | re.DOTALL)
        if dp:
            headline = re.sub(r'\s+Vial\b', '', dp.group(1)).strip()
            subhead  = 'Dosage Protocol'
    else:
        qs = re.match(r'^(.+?\?)\s+(.+)$', title, re.DOTALL)
        cs = re.match(r'^(.+?):\s+(.+)$', title, re.DOTALL)
        if qs:
            headline, subhead = qs.group(1), qs.group(2)
        elif cs:
            headline = cs.group(1).rstrip(':').strip()
            subhead  = cs.group(2)

    new_h1 = (f'<h1 style="font-size:1.75rem;line-height:1.25;margin-bottom:.2rem">'
              f'{headline}</h1>')
    if subhead:
        new_h1 += f'\n<p class="page-subhead">{subhead}</p>'

    return content[:m.start()] + new_h1 + content[m.end():]


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
    # Fall back to raw if file is just a <main> block (no <body> wrapper)
    search_in = body_html if body_html else raw

    # Try to get <main> content
    main_html = extract(r'(<main[^>]*>.*?</main>)', search_in)
    if not main_html:
        # Some WP exports omit </main>; grab from <main> to end of body
        main_html = extract(r'(<main[^>]*>.*)', search_in)
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

    # Count <article> elements — if multiple, use full <main> content
    # (dosage protocol pages use multiple <article> cards inside <main>)
    article_count = len(re.findall(r'<article[\s>]', main_html))

    if article_count == 1:
        # Single article page (e.g. what-is-* articles) — extract article content
        article = extract(r'<article[^>]*>(.*?)</article>', main_html)
        if article:
            return article.strip()

    # Multiple articles or no articles: use full <main> inner content
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
    content = strip_broken_links(content)
    content = sanitize_old_branding(content)
    content = strip_sponsor_sections(content)
    content = strip_hero_image(content)

    # ── Clean AI-generated jargon from headers ───────────────────────────────
    slug = src_path.parent.name if src_path.name == 'index.html' else src_path.stem
    is_article_or_educational = (slug.startswith('what-is') or slug.startswith('what-are')
                                  or slug in ('combine-peptides-same-syringe',
                                              'retatrutide-vs-tirzepatide',
                                              'tesamorelin-reconstitution-storage'))
    if is_article_or_educational:
        content = clean_headers(content)
        content = inject_article_image(content, slug)

    # ── Update legal page dates to February 20, 2026 ─────────────────────────
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
    is_dosage = ('dosage-protocol' in slug or 'vial-dosage' in slug
                 or re.match(r'retatrutide-\d+mg$', slug))
    is_educational = slug in ('combine-peptides-same-syringe', 'retatrutide-vs-tirzepatide',
                              'tesamorelin-reconstitution-storage')
    if is_article or is_dosage or is_educational:
        content = rewrite_page_heading(content, slug)
    if is_article or is_dosage or is_educational:
        peptide_name = derive_peptide_name(slug)
        content = inject_inline_sponsor_link(content, sponsor_url, peptide_name)
        content = inject_sponsor_cta(content, sponsor_url, peptide_name)

    # Inject Related Reading cross-links for dosage protocol and article pages
    if is_dosage or is_article or is_educational:
        content = inject_related_reading(content, slug, is_dosage)

    # Inject structured data (Schema.org Microdata) for rich snippets
    if is_dosage:
        content = inject_howto_schema(content, slug)
    elif is_article or is_educational:
        content = inject_faq_schema(content)

    # Strip inline <style> from contact page (styles are in WP global CSS)
    if slug == 'contact-us':
        content = re.sub(r'<style>.*?</style>\s*', '', content, flags=re.DOTALL)

    content = add_lazy_loading(content)
    content = wrap_tables(content)
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
             'wp-content', 'wp-includes', 'pep-dose-favicon-plugin',
             '_dist 2', '_dist 3', 'category'}

# Files without .html extension that are actually HTML pages
BARE_HTML_FILES = [
    'about-us', 'contact-us', 'cookie-policy', 'disclaimer',
    'privacy-policy', 'terms-conditions',
    'peptide-stack-dosages',
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
    """Convert a protocol directory name to a display-friendly title.
    E.g. 'bpc-157-5mg-vial-dosage-protocol' → 'BPC-157 — 5 mg Vial'"""
    name = dirname.replace('-vial-dosage-protocol', '').replace('-dosage-protocol', '')
    # Match "<peptide>-<dose><mg>" pattern, e.g. "bpc-157-5mg" or "ghk-cu-70-mg"
    m = re.match(r'^(.+?)-(\d+(?:\.\d+)?)-?(m?g)$', name)
    if m:
        peptide = _fix_peptide_name_case(m.group(1).replace('-', ' ').title())
        dose    = m.group(2) + ' ' + m.group(3)
        return f'{peptide} — {dose} Vial'
    return _fix_peptide_name_case(name.replace('-', ' ').title())


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
Browse our complete library of {total} peptide dosage protocols. Each protocol includes reconstitution instructions, recommended dosing schedules, and syringe measurements.
</p>
{''.join(all_cards)}'''

    dst = DIST_DIR / 'dosages' / 'index.html'
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(content, encoding='utf-8')
    return True


# ─────────────────────────────────────────────────────────────────────────────
# Static blog/articles listing page (categorised list format)
# ─────────────────────────────────────────────────────────────────────────────
# Slugs to exclude from the articles listing (non-article pages)
_BLOG_EXCLUDE = {'about-us', 'contact-us', 'cookie-policy', 'disclaimer',
                 'privacy-policy', 'terms-conditions', 'dosages', 'blog',
                 'home', 'peptide-dosage-calculator', 'category',
                 'peptide-stack-dosages'}
# Parent directories for dosage protocols (listed on dosages page, not articles)
_DOSAGE_PARENT_DIRS = {'single-peptide-dosages', 'peptide-blend-dosages',
                       'peptide-stack-dosages'}

# Article categories — loaded from _theme/content.json
_ARTICLE_CATEGORIES = [
    (cat['label'], cat['slugs'])
    for cat in CONTENT.get('article_categories', [])
]


def _match_article_to_category(slug):
    """Return category name for a slug, or None if uncategorised."""
    for cat_name, slug_prefixes in _ARTICLE_CATEGORIES:
        for prefix in slug_prefixes:
            if slug.startswith(prefix):
                return cat_name
    return None


def build_blog_page():
    """Generate a static articles listing page with ALL articles, organised by category."""
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
        live_slug = _DIR_TO_LIVE_SLUG.get(slug, slug)
        url = f'/{live_slug}/'
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

    # Group into categories
    categorised = {}  # cat_name → [(title, url, slug)]
    uncategorised = []
    for title, url, slug in articles:
        cat = _match_article_to_category(slug)
        if cat:
            categorised.setdefault(cat, []).append((title, url, slug))
        else:
            uncategorised.append((title, url, slug))

    # Sort articles within each category alphabetically
    for cat in categorised:
        categorised[cat].sort(key=lambda x: x[0].lower())
    uncategorised.sort(key=lambda x: x[0].lower())

    # Build HTML — organised lists by category
    sections_html = ''
    for cat_name, _ in _ARTICLE_CATEGORIES:
        items = categorised.get(cat_name, [])
        if not items:
            continue
        list_items = ''
        for title, url, slug in items:
            list_items += f'<li style="padding:8px 0;border-bottom:1px solid #eee"><a href="{url}" style="color:#2e2a22;text-decoration:none;font-size:1rem">{html_mod.escape(title)}</a></li>\n'
        sections_html += f'''<div style="margin-bottom:2rem">
<h2 style="font-size:1.15rem;color:#2e2a22;margin:0 0 .75rem;padding-bottom:.5rem;border-bottom:2px solid #c85a30">{cat_name} <span style="font-weight:400;color:#6b7280;font-size:.9rem">({len(items)})</span></h2>
<ul style="list-style:none;padding:0;margin:0">
{list_items}</ul>
</div>\n'''

    # Add uncategorised if any
    if uncategorised:
        list_items = ''
        for title, url, slug in uncategorised:
            list_items += f'<li style="padding:8px 0;border-bottom:1px solid #eee"><a href="{url}" style="color:#2e2a22;text-decoration:none;font-size:1rem">{html_mod.escape(title)}</a></li>\n'
        sections_html += f'''<div style="margin-bottom:2rem">
<h2 style="font-size:1.15rem;color:#2e2a22;margin:0 0 .75rem;padding-bottom:.5rem;border-bottom:2px solid #c85a30">Other Articles <span style="font-weight:400;color:#6b7280;font-size:.9rem">({len(uncategorised)})</span></h2>
<ul style="list-style:none;padding:0;margin:0">
{list_items}</ul>
</div>\n'''

    total = len(articles)
    content = f'''<h1>Education &amp; Articles</h1>
<p style="max-width:700px;margin:0 auto 2rem;text-align:center;color:#6b7280;font-size:1.05rem">
Explore our complete library of {total} peptide education articles, organised by topic. Each article provides evidence-based information about mechanisms, benefits, dosing, and safety.
</p>
{sections_html}'''

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
