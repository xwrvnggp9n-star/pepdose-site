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
    'dosages-and-protocols': 'dosages',
    'articles':              'blog',
}


def resolve_slug(slug):
    """Resolve a WP slug to the actual dist directory name."""
    return SLUG_ALIASES.get(slug, slug)


# ── SEO meta descriptions ────────────────────────────────────────────────────
# Custom meta descriptions for SERP appearance. Max ~155 chars for Google display.
_SEO_DESCRIPTIONS = {
    # Homepage & nav pages
    'home':                       'Clear dosage protocols, reconstitution guides, and a free calculator for BPC-157, Semaglutide, Tirzepatide, TB-500, and more peptides.',
    'dosages-and-protocols':      'Browse 15+ peptide dosage protocols with reconstitution instructions, injection schedules, and syringe measurements for every vial size.',
    'articles':                   'Evidence-based peptide education articles covering mechanisms, benefits, dosing, and safety for BPC-157, Semaglutide, Tirzepatide, and more.',
    'peptide-dosage-calculator':  'Free peptide dosage calculator. Enter vial size and water volume to get exact syringe units, concentration, and doses per vial.',
    'about-us':                   'About pep-dose.com — an independent peptide education resource providing clear, evidence-based dosage protocols and research information.',
    'contact-us':                 'Contact the pep-dose.com team with questions about peptide dosages, protocols, or site content.',
    # Education articles
    'what-are-peptides':                     'What are peptides? A practical, evidence-based guide to peptide types, mechanisms of action, administration methods, and safety considerations.',
    'what-is-bpc-157':                       'What is BPC-157? Learn about this healing peptide — mechanism of action, tissue repair benefits, dosing guidelines, and safety profile.',
    'what-is-tb-500':                        'What is TB-500 (Thymosin Beta-4 Fragment)? Mechanism of action, tissue repair benefits, recommended dosing, and safety considerations.',
    'what-is-ghk-cu':                        'What is GHK-Cu? Copper peptide for skin, hair, and tissue regeneration. Mechanism, evidence-based benefits, dosage guide, and risks.',
    'what-is-semaglutide':                   'What is Semaglutide? GLP-1 receptor agonist for weight loss. Mechanism, clinical benefits, dosing protocols, and side effects explained.',
    'what-is-tirzepatide':                   'What is Tirzepatide (Mounjaro/Zepbound)? Dual GIP/GLP-1 agonist mechanism, weight loss results, dosing schedule, and side effects.',
    'what-is-retatrutide':                   'What is Retatrutide? Triple-receptor agonist (GLP-1/GIP/Glucagon) for weight loss. Mechanism, clinical trial data, and dosing guidance.',
    'what-is-tesamorelin':                   'What is Tesamorelin? Growth hormone-releasing hormone analog. Benefits for visceral fat, mechanism, dosing, and side effects.',
    'what-is-ipamorelin':                    'What is Ipamorelin? Selective growth hormone secretagogue. Mechanism, anti-aging benefits, dosage guide, and safety profile.',
    'what-is-mots-c':                        'What is MOTS-c? Mitochondrial peptide for metabolism and longevity. Mechanism, exercise-mimetic benefits, dosing, and research.',
    'what-is-kpv-peptide':                   'What is KPV? Anti-inflammatory peptide for gut health, skin conditions, and immune modulation. Mechanism, benefits, and dosing.',
    'what-is-selank':                        'What is Selank? Nootropic peptide for anxiety and cognition. Mechanism of action, clinical benefits, dosing, and safety profile.',
    'what-is-dsip':                          'What is DSIP (Delta Sleep-Inducing Peptide)? How it promotes deep delta-wave sleep, its mechanism, human clinical evidence, dosing, and safety.',
    'what-is-mazdutide':                     'What is Mazdutide? GLP-1/Glucagon dual agonist peptide for weight loss. Mechanism, clinical data, and comparison to other GLP-1s.',
    'what-is-glp-1':                         'What is GLP-1? Complete guide to glucagon-like peptide-1 — natural function, receptor agonist drugs, weight loss, and diabetes management.',
    'what-is-5-amino-1mq':                   'What is 5-Amino-1MQ? NNMT inhibitor for fat metabolism. Mechanism, weight loss benefits, oral dosing, and current research.',
    'what-is-mgf':                           'What is MGF (Mechano Growth Factor)? Muscle repair peptide — mechanism, benefits for recovery and hypertrophy, dosing guide.',
    'what-is-pnc-27':                        'What is PNC-27? Anti-cancer peptide targeting HDM-2. Mechanism, research on tumor cell destruction, and current status.',
    'what-is-livagen':                       'What is Livagen? Bioregulator peptide for liver health and DNA repair. Mechanism, epigenetic benefits, and dosage information.',
    'what-is-ovagen':                        'What is Ovagen? Liver bioregulator peptide for hepatoprotection. Mechanism, benefits, dosing protocols, and safety information.',
    'what-is-prostamax':                     'What is Prostamax? Prostate bioregulator peptide. Mechanism of action, prostate health benefits, dosing, and research evidence.',
    'what-is-vesugen':                       'What is Vesugen? Vascular bioregulator peptide for cardiovascular health. Mechanism, benefits for blood vessels, and dosing guide.',
    'what-is-vilon':                         'What is Vilon? Lysylglutamic acid peptide for immune modulation. Mechanism, thymus support benefits, and dosing protocols.',
    'what-is-glow-peptide-blend':            'What is the GLOW peptide blend? GHK-Cu + TB-500 + BPC-157 regeneration stack. Components, synergy, dosing, and benefits.',
    'what-is-klow-peptide-blend':            'What is the KLOW peptide blend? GHK-Cu + TB-500 + BPC-157 + KPV stack. Components, anti-inflammatory benefits, and dosing.',
    'what-is-the-wolverine-stack':           'What is the Wolverine Stack? BPC-157 + TB-500 healing peptide combination. Synergy, tissue repair benefits, and dosing guide.',
    'combine-peptides-same-syringe':         'Can you combine peptides in the same syringe? Compatibility guide for mixing BPC-157, TB-500, GHK-Cu, and other peptides safely.',
    'retatrutide-vs-tirzepatide':            'Retatrutide vs Tirzepatide comparison. Triple agonist vs dual agonist — weight loss data, mechanisms, side effects, and dosing.',
    'tesamorelin-reconstitution-storage':    'How to store reconstituted Tesamorelin. Temperature, shelf life, bacteriostatic water guidelines, and best practices.',
    # Dosage protocols
    'bpc-157-5mg-vial-dosage-protocol':      'BPC-157 5mg vial dosage protocol. Reconstitution, injection schedule, syringe measurements, and recommended dosing for healing.',
    'bpc-157-10mg-vial-dosage-protocol':     'BPC-157 10mg vial dosage protocol. Reconstitution with bacteriostatic water, injection dosing, syringe units, and schedule.',
    'ghk-cu-50mg-vial-dosage-protocol':      'GHK-Cu 50mg vial dosage protocol. Reconstitution guide, injection schedule, syringe measurements, and copper peptide dosing.',
    'ghk-cu-100mg-vial-dosage-protocol':     'GHK-Cu 100mg vial dosage protocol. Reconstitution, recommended doses, syringe units, and injection frequency guide.',
    'tb-500-5mg-vial-dosage-protocol':       'TB-500 5mg vial dosage protocol. Reconstitution instructions, loading and maintenance dosing, and syringe measurements.',
    'tb-500-10mg-vial-dosage-protocol':      'TB-500 10mg vial dosage protocol. Reconstitution, injection schedule, syringe units, and tissue repair dosing guide.',
    'sema-5mg-vial-dosage-protocol':         'Semaglutide 5mg vial dosage protocol. Reconstitution, weekly injection schedule, dose titration, and syringe measurements.',
    'sema-10mg-vial-dosage-protocol':        'Semaglutide 10mg vial dosage protocol. Reconstitution guide, dose escalation schedule, syringe units, and weekly dosing.',
    'tesamorelin-5mg-vial-dosage-protocol':  'Tesamorelin 5mg vial dosage protocol. Reconstitution, daily injection schedule, syringe measurements, and storage guidance.',
    'tesamorelin-10mg-vial-dosage-protocol': 'Tesamorelin 10mg vial dosage protocol. Reconstitution, daily dosing, syringe units, and growth hormone release guide.',
    'tirzepatide-10mg-vial-dosage-protocol': 'Tirzepatide 10mg vial dosage protocol. Reconstitution, weekly dose titration schedule, syringe measurements, and guidance.',
    'mots-c-10mg-vial-dosage-protocol':      'MOTS-c 10mg vial dosage protocol. Reconstitution, injection schedule, syringe units, and mitochondrial peptide dosing.',
    'retatrutide-5mg':                       'Retatrutide 5mg vial dosage protocol. Reconstitution, weekly dosing schedule, syringe measurements, and titration guide.',
    'retatrutide-10mg':                      'Retatrutide 10mg vial dosage protocol. Reconstitution, dose escalation, syringe units, and triple agonist dosing guide.',
    'retatrutide-30mg':                      'Retatrutide 30mg vial dosage protocol. Reconstitution, weekly injection schedule, syringe measurements, and dosing guide.',
    'glow-70-mg-vial-dosage-protocol':       'GLOW 70mg peptide blend dosage protocol. GHK-Cu + TB-500 + BPC-157 reconstitution, injection schedule, and syringe guide.',
    'klow-80mg-vial-dosage-protocol':        'KLOW 80mg peptide blend dosage protocol. GHK-Cu + TB-500 + BPC-157 + KPV reconstitution, dosing, and syringe guide.',
    'wolverine-stack-20mg-vial-dosage-protocol': 'Wolverine Stack 20mg dosage protocol. BPC-157 + TB-500 reconstitution, injection schedule, and syringe measurements.',
    'dsip-5mg-vial-dosage-protocol':              'DSIP 5mg vial dosage protocol. Reconstitute with 2.0 mL bacteriostatic water for 2.5 mg/mL. Starting: 100 mcg; standard: 200 mcg. Inject 30–60 min before sleep.',
    'what-is-pt-141':                             'What is PT-141 (Bremelanotide)? FDA-approved melanocortin peptide for sexual desire. Mechanism, clinical evidence, dosing, and safety.',
    'pt-141-10mg-vial-dosage-protocol':           'PT-141 10mg vial dosage protocol. Reconstitute with 3.0 mL BAC water for 3.33 mg/mL. Research dosing 500–1,750 mcg SC 30–45 min before activity.',
    'what-is-melanotan-ii':                       'What is Melanotan II? Non-selective melanocortin agonist for tanning and sexual function research. Mechanism, evidence, dosing, and safety risks.',
    'melanotan-ii-10mg-vial-dosage-protocol':     'Melanotan II 10mg vial dosage protocol. Reconstitute with 3.0 mL BAC water for 3.33 mg/mL. Loading: 250–1,000 mcg/day SC. Safety ceiling: 2 mg/day.',
    'what-is-oxytocin':                           'What is Oxytocin? The bonding neuropeptide — social trust, anxiety, and neurological research. Mechanism, evidence, dosing, and safety.',
    'oxytocin-5mg-vial-dosage-protocol':          'Oxytocin 5mg vial dosage protocol. Reconstitute with 3.0 mL BAC water for 1.67 mg/mL. Research dosing 100–500 mcg SC, titrated over 12 weeks.',
    'kpv-10mg-vial-dosage-protocol':              'KPV 10mg vial dosage protocol. Reconstitute with 3.0 mL BAC water for 3.33 mg/mL. Titrate 200–500 mcg/day SC. 20 doses per vial at maintenance.',
    'tirzepatide-30mg-vial-dosage-protocol':      'Tirzepatide 30mg vial dosage protocol. Reconstitute with 3.0 mL BAC water for 10.0 mg/mL. Weekly SC injection, 2.5–15 mg titration over 20+ weeks.',
}


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
