#!/usr/bin/env python3
"""
pep-dose.com — Site Verification Test Suite
=============================================
Run after build + deploy to verify everything is correct.

USAGE:
    python3 tests.py              — run all tests (build + live)
    python3 tests.py --build      — only check _dist/ build output
    python3 tests.py --live       — only check live site via HTTP
    python3 tests.py -v           — verbose output
"""

import json
import os
import re
import sys
import urllib.request
import urllib.error
from pathlib import Path

# ─────────────────────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────────────────────
BASE = Path(__file__).parent
DIST = BASE / '_dist'
CONFIG = json.loads((BASE / '_theme' / 'config.json').read_text())
LIVE_URL = 'https://pep-dose.com'

VERBOSE = '-v' in sys.argv or '--verbose' in sys.argv
MODE = 'all'
if '--build' in sys.argv:
    MODE = 'build'
elif '--live' in sys.argv:
    MODE = 'live'

# ─────────────────────────────────────────────────────────────────────────────
# Test infrastructure
# ─────────────────────────────────────────────────────────────────────────────
_pass = 0
_fail = 0
_errors = []


def check(condition, description, detail=''):
    global _pass, _fail
    if condition:
        _pass += 1
        if VERBOSE:
            print(f'  ✓  {description}')
    else:
        _fail += 1
        msg = f'  ✗  {description}'
        if detail:
            msg += f'  — {detail}'
        print(msg)
        _errors.append(description)


def section(title):
    print(f'\n{"─"*60}\n  {title}\n{"─"*60}')


def read_dist(slug):
    """Read a _dist file by slug. Returns content string or None."""
    path = DIST / slug / 'index.html'
    if path.exists():
        return path.read_text(encoding='utf-8')
    return None


def fetch_live(path, timeout=15):
    """Fetch a live page. Returns (status_code, body_text) or (None, error)."""
    url = f'{LIVE_URL}{path}'
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'pep-dose-tests/1.0'})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode('utf-8', errors='replace')
    except urllib.error.HTTPError as e:
        return e.code, ''
    except Exception as e:
        return None, str(e)


# ═════════════════════════════════════════════════════════════════════════════
# BUILD TESTS — verify _dist/ output is correct
# ═════════════════════════════════════════════════════════════════════════════

def test_build_dist_exists():
    section('Build: _dist/ structure')
    check(DIST.exists(), '_dist/ directory exists')
    check((DIST / 'blog' / 'index.html').exists(), '_dist/blog/index.html exists')
    check((DIST / 'dosages' / 'index.html').exists(), '_dist/dosages/index.html exists')
    check((DIST / 'peptide-dosage-calculator' / 'index.html').exists(),
          '_dist/peptide-dosage-calculator/index.html exists')
    check((DIST / 'about-us' / 'index.html').exists(), '_dist/about-us/index.html exists')
    check((DIST / 'contact-us' / 'index.html').exists(), '_dist/contact-us/index.html exists')
    check((DIST / 'calculator-widget.html').exists(), 'calculator-widget.html copied')
    check((DIST / 'robots.txt').exists(), 'robots.txt copied')
    check((DIST / 'sitemap.xml').exists(), 'sitemap.xml copied')


def test_build_no_purelab():
    section('Build: No PureLab references')
    offending = []
    for f in DIST.rglob('*.html'):
        content = f.read_text(encoding='utf-8', errors='replace')
        if 'purelabpeptides' in content.lower() or 'peptidedosages.com' in content.lower():
            offending.append(str(f.relative_to(DIST)))
    check(len(offending) == 0, 'No PureLab/peptidedosages references in _dist/',
          f'Found in: {", ".join(offending[:5])}' if offending else '')


def test_build_no_template_literals():
    section('Build: No JS template literals in output')
    offending = []
    for f in DIST.rglob('*.html'):
        content = f.read_text(encoding='utf-8', errors='replace')
        if '${' in content and f.name != 'calculator-widget.html':
            offending.append(str(f.relative_to(DIST)))
    check(len(offending) == 0, 'No ${...} template literals in built pages',
          f'Found in: {", ".join(offending[:5])}' if offending else '')


def test_build_articles_have_titles():
    section('Build: Articles have <h1> titles')
    article_dirs = [d for d in DIST.iterdir()
                    if d.is_dir() and (d.name.startswith('what-is') or d.name.startswith('what-are'))]
    missing = []
    for d in article_dirs:
        content = read_dist(d.name)
        if content and not re.search(r'<h1[\s>]', content):
            missing.append(d.name)
    check(len(missing) == 0, f'All {len(article_dirs)} articles have <h1> titles',
          f'Missing in: {", ".join(missing[:5])}' if missing else '')


def test_build_dosage_pages_have_titles():
    section('Build: Dosage protocol pages have titles')
    missing = []
    for parent in ['single-peptide-dosages', 'peptide-blend-dosages']:
        parent_dir = DIST / parent
        if not parent_dir.exists():
            continue
        for d in parent_dir.iterdir():
            if not d.is_dir():
                continue
            idx = d / 'index.html'
            if idx.exists():
                content = idx.read_text(encoding='utf-8', errors='replace')
                if not re.search(r'<h1[\s>]', content):
                    missing.append(f'{parent}/{d.name}')
    check(len(missing) == 0, 'All dosage protocol pages have <h1> titles',
          f'Missing in: {", ".join(missing[:5])}' if missing else '')


def test_build_sponsor_injection():
    section('Build: Sponsor CTA injection')
    # Articles that should have sponsors
    article_dirs = [d for d in DIST.iterdir()
                    if d.is_dir() and (d.name.startswith('what-is') or d.name.startswith('what-are'))]
    missing_cta = []
    missing_inline = []
    for d in article_dirs:
        content = read_dist(d.name)
        if not content:
            continue
        if 'sponsor-cta' not in content:
            missing_cta.append(d.name)
        if 'whitemarketpeptides.com' not in content:
            missing_inline.append(d.name)
    check(len(missing_cta) == 0,
          f'All {len(article_dirs)} articles have sponsor CTA block',
          f'Missing: {", ".join(missing_cta[:5])}' if missing_cta else '')
    check(len(missing_inline) == 0,
          f'All {len(article_dirs)} articles have WMP links',
          f'Missing: {", ".join(missing_inline[:5])}' if missing_inline else '')

    # Dosage protocols should also have sponsors
    dosage_missing = []
    for parent in ['single-peptide-dosages', 'peptide-blend-dosages']:
        parent_dir = DIST / parent
        if not parent_dir.exists():
            continue
        for d in parent_dir.iterdir():
            if not d.is_dir():
                continue
            idx = d / 'index.html'
            if idx.exists():
                content = idx.read_text(encoding='utf-8', errors='replace')
                if 'sponsor-cta' not in content:
                    dosage_missing.append(f'{parent}/{d.name}')
    check(len(dosage_missing) == 0,
          'All dosage protocol pages have sponsor CTA',
          f'Missing: {", ".join(dosage_missing[:5])}' if dosage_missing else '')


def test_build_sponsor_utm_tags():
    section('Build: Sponsor links have UTM tags')
    bad_links = []
    for f in DIST.rglob('*.html'):
        content = f.read_text(encoding='utf-8', errors='replace')
        # Find all WMP links
        for m in re.finditer(r'href="(https://whitemarketpeptides\.com[^"]*)"', content):
            url = m.group(1)
            if 'utm_source=pep-dose' not in url:
                rel = str(f.relative_to(DIST))
                if rel not in bad_links:
                    bad_links.append(rel)
    check(len(bad_links) == 0, 'All WMP links have UTM tags',
          f'Missing UTM in: {", ".join(bad_links[:5])}' if bad_links else '')


def test_build_sponsor_coupon_code():
    section('Build: Sponsor coupon code PEPDOSE present')
    article_dirs = [d for d in DIST.iterdir()
                    if d.is_dir() and (d.name.startswith('what-is') or d.name.startswith('what-are'))]
    missing = []
    for d in article_dirs:
        content = read_dist(d.name)
        if content and 'PEPDOSE' not in content:
            missing.append(d.name)
    check(len(missing) == 0, 'All articles mention coupon code PEPDOSE',
          f'Missing: {", ".join(missing[:5])}' if missing else '')


def test_build_blog_listing():
    section('Build: Blog/articles listing page')
    content = read_dist('blog')
    check(content is not None, 'Blog listing page exists')
    if content:
        # Count article links (list items with links to article pages)
        links = re.findall(r'<li[^>]*><a href="/[^"]+/"', content)
        check(len(links) >= 25, f'Blog lists ≥25 articles (found {len(links)})')
        check('Education &amp; Articles' in content, 'Blog page has correct heading')
        # No pagination
        check('page 2' not in content.lower() and 'next page' not in content.lower(),
              'Blog page has no pagination')


def test_build_dosages_listing():
    section('Build: Dosages catalog page')
    content = read_dist('dosages')
    check(content is not None, 'Dosages catalog page exists')
    if content:
        check('Dosages &amp; Protocols' in content, 'Dosages page has correct heading')
        # Should have protocol links
        links = re.findall(r'href="/(?:single|peptide-blend|peptide-stack)-', content)
        check(len(links) >= 10, f'Dosages page lists ≥10 protocols (found {len(links)})')
        # No ${} template literals
        check('${' not in content, 'No template literals in dosages page')


def test_build_legal_dates():
    section('Build: Legal page dates')
    for slug in ('disclaimer', 'privacy-policy', 'terms-conditions', 'cookie-policy'):
        content = read_dist(slug)
        if content:
            check('February 20, 2026' in content,
                  f'{slug} has date February 20, 2026')


def test_build_colors():
    section('Build: Color replacements applied')
    old_colors = ['#2c3e50', '#34495e', '#1a252f']
    offending = []
    for f in DIST.rglob('*.html'):
        if f.name == 'calculator-widget.html':
            continue
        content = f.read_text(encoding='utf-8', errors='replace').lower()
        for color in old_colors:
            if color in content:
                offending.append(f'{f.relative_to(DIST)}: {color}')
    check(len(offending) == 0, 'No old color codes remain',
          f'Found: {", ".join(offending[:3])}' if offending else '')


def test_build_internal_links():
    section('Build: Internal links are relative')
    offending = []
    for f in DIST.rglob('*.html'):
        content = f.read_text(encoding='utf-8', errors='replace')
        # Check for absolute pep-dose.com links that should be relative
        abs_links = re.findall(r'href="https://pep-dose\.com/[^"]*"', content)
        if abs_links:
            offending.append(str(f.relative_to(DIST)))
    check(len(offending) == 0, 'All internal links are relative (no absolute pep-dose.com URLs)',
          f'Found in: {", ".join(offending[:5])}' if offending else '')


def test_build_no_personal_email():
    section('Build: No personal email')
    offending = []
    for f in DIST.rglob('*.html'):
        content = f.read_text(encoding='utf-8', errors='replace')
        if 'sec9vzion' in content.lower():
            offending.append(str(f.relative_to(DIST)))
    check(len(offending) == 0, 'No sec9vzion email in any page',
          f'Found in: {", ".join(offending[:5])}' if offending else '')


def test_build_content_quality():
    section('Build: Content quality (no broken/placeholder content)')
    # Check for "Content unavailable" placeholder
    broken = []
    for f in DIST.rglob('*.html'):
        if f.name == 'calculator-widget.html':
            continue
        content = f.read_text(encoding='utf-8', errors='replace')
        if 'Content unavailable' in content:
            broken.append(str(f.relative_to(DIST)))
    check(len(broken) == 0, 'No pages with "Content unavailable" placeholder',
          f'Found in: {", ".join(broken)}' if broken else '')

    # Check all dosage protocol pages have real protocol content
    protocol_missing = []
    for parent in ['single-peptide-dosages', 'peptide-blend-dosages']:
        parent_dir = DIST / parent
        if not parent_dir.exists():
            continue
        for d in parent_dir.iterdir():
            if not d.is_dir():
                continue
            idx = d / 'index.html'
            if idx.exists():
                content = idx.read_text(encoding='utf-8', errors='replace')
                if ('Protocol Overview' not in content and 'Dosing Protocol' not in content
                        and 'Overview' not in content and 'Dosing Details' not in content):
                    protocol_missing.append(f'{parent}/{d.name}')
    check(len(protocol_missing) == 0,
          'All dosage protocols have real content (Overview or Dosing Details)',
          f'Missing: {", ".join(protocol_missing)}' if protocol_missing else '')

    # Check no stale pagination pages in _dist
    pagination = list(DIST.glob('**/page/*/index.html'))
    check(len(pagination) == 0, 'No stale pagination pages in _dist/',
          f'Found: {[str(p.relative_to(DIST)) for p in pagination]}' if pagination else '')


def test_build_live_page_content():
    section('Build: All deployed pages have substantial content')
    # Every dist page should have at least an <h1> or <h2> or <h3> and some text
    thin_pages = []
    for f in DIST.rglob('index.html'):
        rel = str(f.relative_to(DIST))
        # Skip category index pages and known small pages
        if '/category/' in rel:
            continue
        content = f.read_text(encoding='utf-8', errors='replace')
        # Must have at least one heading
        if not re.search(r'<h[1-3][\s>]', content):
            thin_pages.append(f'{rel} (no heading)')
        # Must have at least 100 chars of actual text (strips tags)
        text_only = re.sub(r'<[^>]+>', '', content).strip()
        if len(text_only) < 100:
            thin_pages.append(f'{rel} (text too short: {len(text_only)} chars)')
    check(len(thin_pages) == 0, 'All pages have headings and substantial text',
          f'Issues: {", ".join(thin_pages[:5])}' if thin_pages else '')


def test_build_calculator_gateway():
    section('Build: Calculator gateway page')
    content = read_dist('peptide-dosage-calculator')
    check(content is not None, 'Calculator gateway page exists')
    if content:
        check('xwrvnggp9n-star.github.io' in content,
              'Calculator links to GitHub Pages widget')
        check('Open Calculator' in content, 'Has "Open Calculator" button')


# ═════════════════════════════════════════════════════════════════════════════
# LIVE SITE TESTS — verify pages on pep-dose.com
# ═════════════════════════════════════════════════════════════════════════════

def test_live_homepage():
    section('Live: Homepage')
    status, body = fetch_live('/')
    check(status == 200, 'Homepage returns 200')
    if body:
        check('pep-dose' in body.lower() or 'pep·dose' in body or 'pd-logo' in body,
              'Homepage contains pep-dose branding')


def test_live_nav_pages():
    section('Live: All nav pages return 200')
    nav_paths = [
        ('/dosages-and-protocols/', 'Dosages & Protocols'),
        ('/articles/', 'Education & Articles'),
        ('/peptide-dosage-calculator/', 'Dosage Calculator'),
        ('/about-us/', 'About Us'),
        ('/contact-us/', 'Contact Us'),
    ]
    for path, name in nav_paths:
        status, body = fetch_live(path)
        check(status == 200, f'{name} ({path}) returns 200',
              f'Got status {status}' if status != 200 else '')


def test_live_legal_pages():
    section('Live: Legal pages return 200')
    for slug in ('disclaimer', 'privacy-policy', 'cookie-policy', 'terms-conditions'):
        status, _ = fetch_live(f'/{slug}/')
        check(status == 200, f'/{slug}/ returns 200',
              f'Got status {status}' if status != 200 else '')


def test_live_dosages_content():
    section('Live: Dosages page has real content (not template literals)')
    status, body = fetch_live('/dosages-and-protocols/')
    if status == 200:
        check('${' not in body, 'No ${} template literals on dosages page',
              'Found raw ${...} in page content' if '${' in body else '')
        check('View Protocol' in body or 'dosage-protocol' in body,
              'Dosages page has protocol links')


def test_live_dosages_catalog_completeness():
    section('Live: Dosages catalog lists every protocol source page')
    status, body = fetch_live('/dosages-and-protocols/')
    if status != 200:
        check(False, f'Dosages catalog returned HTTP {status}')
        return
    missing = []
    for parent in ('single-peptide-dosages', 'peptide-blend-dosages', 'peptide-stack-dosages'):
        d = BASE / parent
        if not d.exists() or not d.is_dir():
            continue
        for child in sorted(d.iterdir()):
            if child.is_dir() and (child / 'index.html').exists():
                slug = child.name
                if slug not in body:
                    missing.append(f'{parent}/{slug}')
    check(len(missing) == 0,
          f'All protocol source dirs appear in live catalog',
          f'Missing from live catalog: {missing}' if missing else '')


def test_live_articles_listing():
    section('Live: Articles listing page')
    status, body = fetch_live('/articles/')
    if status == 200:
        # WP renders this page via its blog template (page_for_posts=101),
        # which means our custom content is in the API but WP renders its
        # own wp-block-query post listing instead. Check for WP blog posts.
        wp_posts = re.findall(r'wp-block-post-title', body)
        custom_cards = re.findall(r'Read Article', body)
        total = len(wp_posts) + len(custom_cards)
        check(total >= 1,
              f'Articles page shows posts (WP template: {len(wp_posts)}, custom: {len(custom_cards)})')
        # Spot check that article content is referenced somewhere
        check('BPC-157' in body or 'bpc-157' in body, 'Articles page references BPC-157')


def test_live_articles_api_content():
    """Check that our custom articles listing is stored correctly in the WP API."""
    section('Live: Articles page API content (stored but may be hidden by WP blog template)')
    status, body = fetch_live('/wp-json/wp/v2/pages/101')
    if status == 200:
        check('Education' in body, 'API: Articles page has Education heading')
        # JSON response has escaped URLs; search for slug patterns
        links = re.findall(r'what-is-[a-z0-9-]+', body)
        check(len(links) >= 20, f'API: Articles page has ≥20 article links (found {len(links)})')


def test_live_sample_articles():
    section('Live: Sample articles load with content')
    articles = [
        ('/what-is-bpc-157/', 'BPC-157'),
        ('/what-is-tb-500/', 'TB-500'),
        ('/what-is-tesamorelin/', 'Tesamorelin'),
    ]
    for path, name in articles:
        status, body = fetch_live(path)
        check(status == 200, f'{name} article returns 200')
        if status == 200:
            check(f'<h1' in body, f'{name} article has <h1> title')
            check('sponsor-cta' in body, f'{name} article has sponsor CTA')
            check('PEPDOSE' in body, f'{name} article has coupon code')
            check('whitemarketpeptides.com' in body, f'{name} article has WMP link')


def test_live_sample_dosage_protocols():
    section('Live: Sample dosage protocols load')
    protocols = [
        '/single-peptide-dosages/bpc-157-5mg-vial-dosage-protocol/',
        '/peptide-blend-dosages/wolverine-stack-20mg-vial-dosage-protocol/',
    ]
    for path in protocols:
        status, body = fetch_live(path)
        check(status == 200, f'{path} returns 200',
              f'Got status {status}' if status != 200 else '')
        if status == 200:
            check('sponsor-cta' in body, f'{path} has sponsor CTA')


def test_live_header_footer():
    section('Live: Header & footer rendering')
    status, body = fetch_live('/about-us/')
    if status == 200:
        check('pd-header' in body, 'Page has pd-header class')
        check('pd-footer' in body, 'Page has pd-footer class')
        check('pd-logo' in body, 'Page has pd-logo')
        check('Poppins' in body, 'Poppins font loaded')
        check('Lora' in body, 'Lora font loaded')


def test_live_search_no_button():
    section('Live: Search box has no button')
    status, body = fetch_live('/')
    if status == 200:
        check('wp-block-search__button' not in body or 'display: none' in body
              or 'display:none' in body or 'no-button' in body,
              'Search button hidden or absent')
        check('search pep-dose' in body.lower() or 'search pep-dose' in body,
              'Search placeholder says "search pep-dose"')


def test_live_no_purelab():
    section('Live: No PureLab references')
    # Spot check a few pages
    for path in ['/what-is-bpc-157/', '/what-is-tb-500/', '/about-us/']:
        status, body = fetch_live(path)
        if status == 200:
            check('purelabpeptides' not in body.lower(),
                  f'No PureLab on {path}')
            check('peptidedosages.com' not in body.lower(),
                  f'No peptidedosages.com on {path}')


def test_live_legal_dates():
    section('Live: Legal page dates')
    for slug in ('disclaimer', 'privacy-policy', 'terms-conditions'):
        status, body = fetch_live(f'/{slug}/')
        if status == 200:
            check('February 20, 2026' in body,
                  f'{slug} shows date February 20, 2026')


def test_live_calculator():
    section('Live: Calculator gateway')
    status, body = fetch_live('/peptide-dosage-calculator/')
    if status == 200:
        check('github.io' in body or 'Open Calculator' in body,
              'Calculator page links to GitHub Pages widget')


def test_live_contact_form():
    section('Live: Contact page has form')
    status, body = fetch_live('/contact-us/')
    if status == 200:
        check('contact-form' in body or 'form-group' in body or '<form' in body,
              'Contact page has form elements')


def test_live_all_dosage_protocols():
    section('Live: All dosage protocol pages have real content')
    # Enumerate dynamically from source dirs so new pages are automatically tested
    protocols = []
    for parent in ('single-peptide-dosages', 'peptide-blend-dosages', 'peptide-stack-dosages'):
        d = BASE / parent
        if not d.exists() or not d.is_dir():
            continue
        for child in sorted(d.iterdir()):
            if child.is_dir() and (child / 'index.html').exists():
                protocols.append(f'/{parent}/{child.name}/')
    for path in protocols:
        status, body = fetch_live(path)
        slug = path.strip('/').split('/')[-1]
        check(status == 200, f'{slug} returns 200',
              f'Got {status}' if status != 200 else '')
        if status == 200:
            check('Content unavailable' not in body,
                  f'{slug} has real content (not placeholder)')
            check('Protocol Overview' in body or 'Dosing Protocol' in body
                  or 'Overview' in body or 'Dosing Details' in body
                  or 'protocol' in body.lower(),
                  f'{slug} has protocol information')


# ═════════════════════════════════════════════════════════════════════════════
# CONFIG VALIDATION TESTS
# ═════════════════════════════════════════════════════════════════════════════

def test_config_validation():
    section('Config: _theme/config.json validation')
    check(CONFIG.get('site_name') == 'pep-dose.com', 'Site name is pep-dose.com')
    check(CONFIG.get('site_url') == 'https://pep-dose.com', 'Site URL correct')

    colors = CONFIG.get('colors', {})
    check(colors.get('header_bg') == '#2e2a22', 'Header bg is warm slate')
    check(colors.get('accent') == '#c85a30', 'Accent is orange')
    check(colors.get('teal') == '#3aaa8c', 'Teal color correct')

    sponsor = CONFIG.get('sponsor', {})
    check(sponsor.get('name') == 'White Market Peptides', 'Sponsor is WMP')
    check(sponsor.get('discount_code') == 'PEPDOSE', 'Coupon code is PEPDOSE')
    check('whitemarketpeptides.com' in sponsor.get('url', ''), 'Sponsor URL correct')

    nav = CONFIG.get('nav', [])
    check(len(nav) == 5, f'Nav has 5 items (found {len(nav)})')
    nav_titles = [item['title'] for item in nav]
    check('Dosages & Protocols' in nav_titles, 'Nav has "Dosages & Protocols"')
    check('Education & Articles' in nav_titles, 'Nav has "Education & Articles"')

    # Check sponsor_links coverage
    links = CONFIG.get('sponsor_links', {})
    check(len(links) >= 15, f'sponsor_links has ≥15 entries (found {len(links)})')
    check('what-is-bpc-157' in links, 'BPC-157 has sponsor link')
    check('what-is-tb-500' in links, 'TB-500 has sponsor link')


# ═════════════════════════════════════════════════════════════════════════════
# Runner
# ═════════════════════════════════════════════════════════════════════════════

BUILD_TESTS = [
    test_build_dist_exists,
    test_build_no_purelab,
    test_build_no_template_literals,
    test_build_articles_have_titles,
    test_build_dosage_pages_have_titles,
    test_build_sponsor_injection,
    test_build_sponsor_utm_tags,
    test_build_sponsor_coupon_code,
    test_build_blog_listing,
    test_build_dosages_listing,
    test_build_legal_dates,
    test_build_colors,
    test_build_internal_links,
    test_build_no_personal_email,
    test_build_content_quality,
    test_build_live_page_content,
    test_build_calculator_gateway,
    test_config_validation,
]

LIVE_TESTS = [
    test_live_homepage,
    test_live_nav_pages,
    test_live_legal_pages,
    test_live_dosages_content,
    test_live_dosages_catalog_completeness,
    test_live_articles_listing,
    test_live_articles_api_content,
    test_live_sample_articles,
    test_live_sample_dosage_protocols,
    test_live_header_footer,
    test_live_search_no_button,
    test_live_no_purelab,
    test_live_legal_dates,
    test_live_calculator,
    test_live_contact_form,
    test_live_all_dosage_protocols,
]


def main():
    print(f'\n{"═"*60}')
    print(f'  pep-dose.com Test Suite')
    print(f'  Mode: {MODE}  {"(verbose)" if VERBOSE else ""}')
    print(f'{"═"*60}')

    if MODE in ('all', 'build'):
        for test in BUILD_TESTS:
            test()

    if MODE in ('all', 'live'):
        for test in LIVE_TESTS:
            test()

    print(f'\n{"═"*60}')
    print(f'  Results: {_pass} passed, {_fail} failed')
    if _errors:
        print(f'\n  Failed tests:')
        for e in _errors:
            print(f'    • {e}')
    print(f'{"═"*60}\n')

    return 0 if _fail == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
