#!/usr/bin/env python3
"""Deploy prepped content from _dist/ to WordPress.com via REST API.

build.py outputs clean article-body HTML to _dist/<slug>/index.html.
This script reads those files and pushes the content to WP pages/posts.

Usage:
    python3 deploy.py              # deploy all pages & posts
    python3 deploy.py about-us     # deploy only the about-us page
    python3 deploy.py --dry-run    # show what would be deployed
"""

import json, os, re, sys, urllib.request, urllib.error, base64
from pathlib import Path

ROOT        = Path(__file__).resolve().parent
DIST        = ROOT / '_dist'
ENV         = ROOT / '.env'
CONFIG_FILE = ROOT / '_theme' / 'config.json'

with open(CONFIG_FILE, encoding='utf-8') as _f:
    C = json.load(_f)

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
        result = wp_request(f'{endpoint}?per_page=100&page={page}&status=any&_fields=id,slug,status,title')
        if not result or not isinstance(result, list) or len(result) == 0:
            break
        items.extend(result)
        if len(result) < 100:
            break
        page += 1
    return items


def read_content(html_path):
    """Read prepped content file. build.py already outputs clean article body."""
    content = html_path.read_text(encoding='utf-8').strip()
    return content if content else None


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
# The -2 suffix aliases come from config.json (single source of truth with build.py).
# Config stores source_dir → live_slug; invert it here for deploy's live_slug → source_dir use.
_slug_aliases = C.get('slug_aliases', {})
SLUG_ALIASES = {live: src for src, live in _slug_aliases.items()}
# Catalog pages: WP slug differs from _dist/ directory name for build reasons
SLUG_ALIASES['dosages-and-protocols'] = 'dosages'
SLUG_ALIASES['articles']              = 'blog'


def resolve_slug(slug):
    """Resolve a WP slug to the actual dist directory name."""
    return SLUG_ALIASES.get(slug, slug)


# ── SEO meta descriptions ────────────────────────────────────────────────────
# Loaded from _theme/config.json → "seo_descriptions". Edit there, not here.
_SEO_DESCRIPTIONS = C.get('seo_descriptions', {})


def generate_excerpt(html_content, max_len=155):
    """Generate a plain-text excerpt from HTML content for SEO."""
    # Strip HTML tags
    text = re.sub(r'<[^>]+>', ' ', html_content)
    # Collapse whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    # Truncate to max_len at word boundary
    if len(text) > max_len:
        text = text[:max_len].rsplit(' ', 1)[0] + '...'
    return text


def get_seo_description(slug, html_content):
    """Get SEO meta description: use custom if available, otherwise auto-generate."""
    # Check direct slug match
    if slug in _SEO_DESCRIPTIONS:
        return _SEO_DESCRIPTIONS[slug]
    # Check resolved/alias slug
    resolved = resolve_slug(slug)
    if resolved in _SEO_DESCRIPTIONS:
        return _SEO_DESCRIPTIONS[resolved]
    # Auto-generate from content
    return generate_excerpt(html_content)


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
    # Track whether catalog pages need redeployment
    deployed_protocol = False
    deployed_article  = False

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

        content = read_content(dist_file)
        if not content:
            print(f'  ✗ Empty content file: {dist_file}')
            errors += 1
            continue

        # Generate SEO description and excerpt
        seo_desc = get_seo_description(slug, content)
        payload = {
            'content': content,
            'excerpt': seo_desc,
            'meta': {
                'advanced_seo_description': seo_desc,
            },
        }

        if dry_run:
            print(f'  [DRY RUN] Would update {wp_type[:-1]} "{title}" (ID: {wp_id}, slug: {slug}) — {len(content)} chars')
            print(f'            SEO desc: {seo_desc[:80]}...')
            updated += 1
            continue

        print(f'  Updating {wp_type[:-1]}: {title} (ID: {wp_id})...', end=' ', flush=True)
        result = wp_request(f'{wp_type}/{wp_id}', method='POST', data=payload)
        if result:
            warnings = result.get('_content_warnings', [])
            if warnings:
                print(f'⚠ updated with warnings: {warnings}')
            else:
                print('✓')
            updated += 1
            # Flag catalog pages for redeployment
            if 'dosage-protocol' in slug or re.match(r'retatrutide-\d+mg$', slug):
                deployed_protocol = True
            if slug.startswith('what-is') or slug.startswith('what-are'):
                deployed_article = True
        else:
            errors += 1

    # Auto-redeploy catalog pages if their content changed
    CATALOG_SLUGS = []
    if deployed_protocol and slug_filter and slug_filter not in ('dosages-and-protocols', 'articles'):
        CATALOG_SLUGS.append('dosages-and-protocols')
    if deployed_article and slug_filter and slug_filter not in ('dosages-and-protocols', 'articles'):
        CATALOG_SLUGS.append('articles')

    for catalog_slug in CATALOG_SLUGS:
        catalog_item = next((p for p in pages if p['slug'] == catalog_slug), None)
        if not catalog_item:
            continue
        resolved = resolve_slug(catalog_slug)
        dist_file = find_dist_file(resolved)
        if not dist_file:
            continue
        content = read_content(dist_file)
        if not content:
            continue
        seo_desc = get_seo_description(catalog_slug, content)
        payload = {'content': content, 'excerpt': seo_desc, 'meta': {'advanced_seo_description': seo_desc}}
        if dry_run:
            print(f'  [DRY RUN] Would also update catalog: {catalog_slug}')
        else:
            print(f'  Auto-updating catalog: {catalog_slug} (ID: {catalog_item["id"]})...', end=' ', flush=True)
            result = wp_request(f'pages/{catalog_item["id"]}', method='POST', data=payload)
            print('✓' if result else '✗')

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
