#!/usr/bin/env python3
"""Deploy built _dist/ content to WordPress.com via REST API.

Usage:
    python3 deploy.py              # deploy all pages & posts
    python3 deploy.py about-us     # deploy only the about-us page
    python3 deploy.py --dry-run    # show what would be deployed
"""

import json, os, re, sys, urllib.request, urllib.error, base64
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DIST = ROOT / '_dist'
ENV  = ROOT / '.env'

# ── Load credentials ──────────────────────────────────────────────────────────
def load_env():
    creds = {}
    if not ENV.exists():
        sys.exit('ERROR: .env file not found. Create it with WP_SITE, WP_USER, WP_APP_PASSWORD.')
    for line in ENV.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        key, _, val = line.partition('=')
        creds[key.strip()] = val.strip()
    return creds

ENV_VARS = load_env()
WP_SITE  = ENV_VARS.get('WP_SITE', '')
WP_USER  = ENV_VARS.get('WP_USER', '')
WP_PASS  = ENV_VARS.get('WP_APP_PASSWORD', '')

if not all([WP_SITE, WP_USER, WP_PASS]):
    sys.exit('ERROR: .env must contain WP_SITE, WP_USER, WP_APP_PASSWORD.')

API_BASE = f'https://{WP_SITE}/wp-json/wp/v2'
AUTH_HEADER = 'Basic ' + base64.b64encode(f'{WP_USER}:{WP_PASS}'.encode()).decode()


# ── WP API helpers ────────────────────────────────────────────────────────────
def wp_request(endpoint, method='GET', data=None):
    url = f'{API_BASE}/{endpoint}'
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, method=method)
    req.add_header('Authorization', AUTH_HEADER)
    if data:
        req.add_header('Content-Type', 'application/json')
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        err_body = e.read().decode()
        print(f'  ✗ HTTP {e.code}: {err_body[:200]}')
        return None


def fetch_all_wp_items(endpoint):
    """Fetch all items from a paginated WP endpoint."""
    items = []
    page = 1
    while True:
        result = wp_request(f'{endpoint}?per_page=100&page={page}&_fields=id,slug,status,title')
        if not result or not isinstance(result, list) or len(result) == 0:
            break
        items.extend(result)
        if len(result) < 100:
            break
        page += 1
    return items


def extract_article_content(html_path):
    """Extract content from between <article> tags in a built HTML file."""
    html = html_path.read_text(encoding='utf-8')
    m = re.search(r'<article[^>]*>(.*?)</article>', html, re.DOTALL)
    if m:
        return m.group(1).strip()
    # Fallback: try <main> content minus wrapping divs
    m = re.search(r'<main[^>]*>(.*?)</main>', html, re.DOTALL)
    if m:
        return m.group(1).strip()
    return None


def find_dist_file(slug):
    """Find the built HTML file for a given slug."""
    # Check direct slug directory
    candidates = [
        DIST / slug / 'index.html',
        # Dosage protocol pages are nested under parent categories
        DIST / 'single-peptide-dosages' / slug / 'index.html',
        DIST / 'peptide-blend-dosages' / slug / 'index.html',
        DIST / 'peptide-stack-dosages' / slug / 'index.html',
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


# ── Slug mapping for WP slugs that differ from source dir names ──────────────
# Some WP posts/pages use slightly different slugs than the source directories.
# This maps WP slug → source directory name when they differ.
SLUG_ALIASES = {
    'what-is-tirzepatide':  'what-is-tirzepatide-2',
    'what-is-ghk-cu':      'what-is-ghk-cu-2',
    'what-is-selank':      'what-is-selank-2',
    'what-is-vilon':       'what-is-vilon-2',
    'what-is-retatrutide':  'what-is-retatrutide-2',
    'retatrutide-5mg-vial-dosage-protocol':  'retatrutide-5mg',
    'retatrutide-10mg-vial-dosage-protocol': 'retatrutide-10mg',
    'retatrutide-30mg-vial-dosage-protocol': 'retatrutide-30mg',
}


def resolve_slug(slug):
    """Resolve a WP slug to the actual dist directory name."""
    return SLUG_ALIASES.get(slug, slug)


# ── Main deploy logic ─────────────────────────────────────────────────────────
def deploy(slug_filter=None, dry_run=False):
    print(f'Fetching pages and posts from {WP_SITE}...')
    pages = fetch_all_wp_items('pages')
    posts = fetch_all_wp_items('posts')

    all_items = [(p, 'pages') for p in pages] + [(p, 'posts') for p in posts]
    print(f'  Found {len(pages)} pages, {len(posts)} posts on WordPress.\n')

    updated = 0
    skipped = 0
    errors  = 0

    for item, wp_type in all_items:
        slug = item['slug']
        wp_id = item['id']
        title = item['title']['rendered']

        if slug_filter and slug != slug_filter:
            continue

        resolved = resolve_slug(slug)
        dist_file = find_dist_file(resolved)

        if not dist_file:
            if slug_filter:
                print(f'  ✗ No built file found for slug "{slug}" (resolved: "{resolved}")')
                errors += 1
            else:
                skipped += 1
            continue

        content = extract_article_content(dist_file)
        if not content:
            print(f'  ✗ Could not extract article content from {dist_file}')
            errors += 1
            continue

        if dry_run:
            print(f'  [DRY RUN] Would update {wp_type[:-1]} "{title}" (ID: {wp_id}, slug: {slug}) — {len(content)} chars')
            updated += 1
            continue

        print(f'  Updating {wp_type[:-1]}: {title} (ID: {wp_id})...', end=' ', flush=True)
        result = wp_request(f'{wp_type}/{wp_id}', method='POST', data={'content': content})
        if result:
            warnings = result.get('_content_warnings', [])
            if warnings:
                print(f'⚠ updated with warnings: {warnings}')
            else:
                print('✓')
            updated += 1
        else:
            errors += 1

    print(f'\n{"[DRY RUN] " if dry_run else ""}Done. {updated} updated, {skipped} skipped (no local file), {errors} errors.')


if __name__ == '__main__':
    slug_filter = None
    dry_run = False

    for arg in sys.argv[1:]:
        if arg == '--dry-run':
            dry_run = True
        else:
            slug_filter = arg

    deploy(slug_filter=slug_filter, dry_run=dry_run)
