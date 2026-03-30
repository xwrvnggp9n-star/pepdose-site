#!/usr/bin/env python3
"""Migrate WP posts (articles) → WP pages to get clean slug URLs without Business plan."""

import json, urllib.request, urllib.error, base64, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ENV  = ROOT / '.env'

creds = {}
for line in ENV.read_text().splitlines():
    line = line.strip()
    if not line or line.startswith('#'): continue
    k, _, v = line.partition('=')
    creds[k.strip()] = v.strip()

WP_SITE = creds['WP_SITE']
WP_USER = creds['WP_USER']
WP_PASS = creds['WP_APP_PASSWORD']
API_BASE = f'https://{WP_SITE}/wp-json/wp/v2'
AUTH_HEADER = 'Basic ' + base64.b64encode(f'{WP_USER}:{WP_PASS}'.encode()).decode()

def wp_request(endpoint, method='GET', data=None):
    url = f'{API_BASE}/{endpoint}'
    body = json.dumps(data).encode() if data else None
    req  = urllib.request.Request(url, data=body, method=method)
    req.add_header('Authorization', AUTH_HEADER)
    if data:
        req.add_header('Content-Type', 'application/json')
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        print(f'  HTTP {e.code}: {e.read().decode()[:200]}')
        return None

# 1. Fetch all posts
print('Fetching posts...')
posts = []
page = 1
while True:
    req = urllib.request.Request(
        f'{API_BASE}/posts?per_page=100&page={page}&_fields=id,slug,title,status,excerpt',
        headers={'Authorization': AUTH_HEADER})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            batch = json.loads(r.read())
    except urllib.error.HTTPError:
        break
    if not batch:
        break
    posts.extend(batch)
    page += 1
print(f'  Found {len(posts)} posts to migrate.\n')

migrated = 0
failed   = 0

for post in posts:
    slug    = post['slug']
    post_id = post['id']
    title   = post['title']['rendered']
    status  = post['status']
    excerpt = post.get('excerpt', {}).get('rendered', '')

    # Read content from _dist
    # Try slug directly, then SLUG_ALIASES lookup
    dist_candidates = [
        ROOT / '_dist' / slug / 'index.html',
    ]
    # Also try what-is-* with -2 suffix source dirs
    content_file = next((p for p in dist_candidates if p.exists()), None)
    if not content_file:
        # Try finding via alias (e.g. what-is-ghk-cu → what-is-ghk-cu-2)
        for d in (ROOT / '_dist').iterdir():
            if d.name.rstrip('0123456789-').rstrip('-') == slug or d.name == slug:
                candidate = d / 'index.html'
                if candidate.exists():
                    content_file = candidate
                    break

    if not content_file:
        print(f'  ✗ [{slug}] No _dist file found — skipping')
        failed += 1
        continue

    content = content_file.read_text(encoding='utf-8')

    print(f'  Migrating: {slug} (post ID {post_id})...')

    # Step 1: Create page with temp slug to avoid conflict
    temp_slug = f'{slug}-migrating'
    new_page = wp_request('pages', method='POST', data={
        'slug':    temp_slug,
        'title':   title,
        'content': content,
        'excerpt': excerpt,
        'status':  status,
    })
    if not new_page:
        print(f'    ✗ Failed to create page for {slug}')
        failed += 1
        continue

    page_id = new_page['id']
    print(f'    Created page ID {page_id} with temp slug "{temp_slug}"')

    # Step 2: Delete old post
    del_result = wp_request(f'posts/{post_id}?force=true', method='DELETE')
    if del_result is None:
        print(f'    ✗ Failed to delete post {post_id} — page {page_id} left with temp slug')
        failed += 1
        continue
    print(f'    Deleted post {post_id}')

    # Step 3: Rename page to correct slug
    updated = wp_request(f'pages/{page_id}', method='POST', data={'slug': slug})
    if not updated:
        print(f'    ✗ Failed to rename page to "{slug}" — left as "{temp_slug}"')
        failed += 1
        continue

    final_link = updated.get('link', '?')
    print(f'    ✓ Page live at: {final_link}')
    migrated += 1
    time.sleep(0.3)  # gentle rate limiting

print(f'\nDone. {migrated} migrated, {failed} failed.')
