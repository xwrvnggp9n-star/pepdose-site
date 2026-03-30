#!/usr/bin/env python3
"""Push updated header/footer template parts to WordPress.com."""

import json, urllib.request, urllib.error, base64
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ENV = ROOT / '.env'

# Load credentials
creds = {}
for line in ENV.read_text().splitlines():
    line = line.strip()
    if not line or line.startswith('#'):
        continue
    key, _, val = line.partition('=')
    creds[key.strip()] = val.strip()

WP_SITE = creds['WP_SITE']
WP_USER = creds['WP_USER']
WP_PASS = creds['WP_APP_PASSWORD']
API_BASE = f'https://{WP_SITE}/wp-json/wp/v2'
AUTH_HEADER = 'Basic ' + base64.b64encode(f'{WP_USER}:{WP_PASS}'.encode()).decode()


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
        print(f'  HTTP {e.code}: {err_body[:500]}')
        return None


# ── Updated header template part ──────────────────────────────────────────────
HEADER_CONTENT = r'''<!-- wp:html -->
<style>
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600;700&family=Lora:ital,wght@0,400;0,600;1,400&display=swap');

/* Fonts */
body { font-family: 'Lora', Georgia, 'Times New Roman', serif !important; }
h1, h2, h3, h4, h5, h6,
.pd-header, .pd-footer,
.wp-block-navigation,
.wp-block-navigation-item,
.wp-block-button__link,
.wp-block-search__button,
.wp-block-search__input { font-family: 'Poppins', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif !important; }

/* Logo — slightly bigger */
.pd-logo { font-family: 'Poppins', sans-serif !important; font-size: clamp(1.5rem, 3vw, 1.9rem); letter-spacing: -.04em; line-height: 1; text-decoration: none !important; display: inline-flex; align-items: baseline; white-space: nowrap; }
.pd-logo-pep { color: #1abc9c; font-weight: 300; }
.pd-logo-sep { color: #e74c3c; font-weight: 700; margin: 0 1px; }
.pd-logo-dose { color: #ffffff; font-weight: 700; }
.pd-footer .pd-logo { font-size: clamp(1.4rem, 2.8vw, 1.8rem); }

/* Header */
.pd-header { background: #2e2a22 !important; position: sticky; top: 0; z-index: 200; box-shadow: 0 2px 10px rgba(0,0,0,.30); }
.pd-header-inner { max-width: 1200px; margin: 0 auto; padding: .75rem 1.5rem; display: flex; align-items: center; justify-content: space-between; flex-wrap: nowrap; gap: 1.5rem; }

/* Navigation spacing */
.pd-header .wp-block-navigation { gap: 0; }
.pd-header .wp-block-navigation-item { margin: 0; }
.pd-header .wp-block-navigation-item a { padding: .5rem .85rem; font-size: .9rem; color: rgba(255,255,255,.85) !important; text-decoration: none; transition: color .2s; }
.pd-header .wp-block-navigation-item a:hover { color: #fff !important; }

/* Search — no button, styled input */
.pd-header .wp-block-search__inside-wrapper { border: none !important; background: transparent !important; }
.pd-header .wp-block-search__input {
  background: rgba(255,255,255,.12) !important;
  border: 1px solid rgba(255,255,255,.18) !important;
  border-radius: 6px !important;
  color: #fff !important;
  padding: .45rem .75rem !important;
  font-size: .85rem !important;
  min-width: 160px;
  transition: background .2s, border-color .2s;
}
.pd-header .wp-block-search__input::placeholder { color: rgba(255,255,255,.45) !important; }
.pd-header .wp-block-search__input:focus {
  background: rgba(255,255,255,.18) !important;
  border-color: rgba(255,255,255,.35) !important;
  outline: none !important;
}
.pd-header .wp-block-search__button { display: none !important; }

/* Footer */
.pd-footer { background: #2e2a22 !important; color: rgba(255,255,255,.60); padding: 3rem 1.5rem 1.25rem; margin-top: 4rem; }
.pd-footer-inner { max-width: 1200px; margin: 0 auto; display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 2rem; align-items: start; }
.pd-footer-brand { display: flex; flex-direction: column; gap: .5rem; }
.pd-footer-tagline { font-size: .83rem; color: rgba(255,255,255,.40); margin: 0; }
.pd-footer-heading { display: block; font-size: .75rem; text-transform: uppercase; letter-spacing: .08em; color: rgba(255,255,255,.35); font-weight: 600; margin-bottom: .6rem; }
.pd-footer-links { list-style: none; margin: 0; padding: 0; }
.pd-footer-links li { margin: .35rem 0; }
.pd-footer-links a { color: rgba(255,255,255,.65); font-size: .85rem; text-decoration: none; }
.pd-footer-links a:hover { color: #fff; }
.pd-footer-copy { border-top: 1px solid rgba(255,255,255,.10); margin-top: 2rem; padding-top: 1rem; font-size: .78rem; text-align: center; color: rgba(255,255,255,.30); max-width: 1200px; margin-left: auto; margin-right: auto; }

/* WP block buttons centered */
.wp-block-buttons.is-content-justification-center { display: flex; justify-content: center; width: 100%; }

/* ── Protocol Page: Consistent Card Styling ── */
.protocol-card,
.section-block,
.important-note {
  background: #fff;
  border: 1px solid #e5e0d5;
  border-left: 3px solid #3aaa8c;
  border-radius: 8px;
  padding: 1.25rem 1.5rem;
  margin-bottom: 1.25rem;
  box-shadow: 0 2px 8px rgba(0,0,0,.06);
}
.protocol-card ul, .protocol-card ol,
.section-block ul, .section-block ol,
.important-note ul, .important-note ol,
.intro-card ul, .intro-card ol,
.dr-container ul, .dr-container ol,
.references-section ul {
  font-family: 'Poppins', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  font-size: .93rem;
  line-height: 1.7;
  padding-left: 1.25rem;
  margin: .5rem 0;
}
.protocol-card li, .section-block li,
.important-note li, .intro-card li,
.dr-container li {
  margin-bottom: .4rem;
  color: #2b2318;
}
.protocol-card p, .section-block p,
.important-note p, .dr-container p {
  font-family: 'Poppins', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  font-size: .93rem;
  line-height: 1.7;
}
.protocol-summary {
  display: grid;
  grid-template-columns: 1fr;
  gap: 0;
}
@media (min-width: 768px) {
  .protocol-summary { grid-template-columns: 1fr 1fr; gap: 1rem; }
}

/* Intro card (At a Glance) */
.intro-card {
  background: #fff;
  border: 1px solid #e5e0d5;
  border-left: 3px solid #3aaa8c;
  border-radius: 8px;
  padding: 1.5rem;
  margin-bottom: 1.5rem;
  box-shadow: 0 2px 8px rgba(0,0,0,.06);
  overflow: hidden;
}
.intro-content { }
.intro-card .intro-image {
  float: right;
  margin: 0 0 .75rem 1.25rem;
}
.intro-image img { width: 160px; height: auto; border-radius: 8px; }

/* Dosing & reconstitution wrapper */
.dosing-recon-wrapper {
  background: #fff;
  border: 1px solid #e5e0d5;
  border-left: 3px solid #c85a30;
  border-radius: 8px;
  padding: 1.5rem;
  margin-bottom: 1.5rem;
  box-shadow: 0 2px 8px rgba(0,0,0,.06);
}
.dr-container { padding: 0; }

/* Dosing table */
.table-responsive { overflow-x: auto; }
.dosing-recon-wrapper table, .dr-container table {
  width: 100%;
  border-collapse: collapse;
  font-family: 'Poppins', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  font-size: .88rem;
  margin: .75rem 0;
}
.dosing-recon-wrapper th, .dr-container th {
  background: #2e2a22;
  color: #fdf8f0;
  padding: .6rem .75rem;
  text-align: left;
  font-weight: 600;
  font-size: .82rem;
  text-transform: uppercase;
  letter-spacing: .03em;
}
.dosing-recon-wrapper td, .dr-container td {
  padding: .55rem .75rem;
  border-bottom: 1px solid #e5e0d5;
  color: #2b2318;
}
.dosing-recon-wrapper tr:nth-child(even) td, .dr-container tr:nth-child(even) td {
  background: #faf5ec;
}

/* References section */
.references-section {
  background: #fff;
  border: 1px solid #e5e0d5;
  border-left: 3px solid #3aaa8c;
  border-radius: 8px;
  padding: 1.25rem 1.5rem;
  margin: 1.5rem 0;
  box-shadow: 0 2px 8px rgba(0,0,0,.06);
}
.reference-list { list-style: none !important; padding-left: 0 !important; }
.reference-list li { padding: .6rem 0; border-bottom: 1px solid #eee; font-size: .85rem; }
.reference-list li:last-child { border-bottom: none; }
.ref-line { margin-bottom: .35rem; }
.ref-line strong { color: #2e2a22; }
.ref-line span { color: #6b7280; }
.ref-button-line { margin-top: .25rem; }
.view-source {
  display: inline-block;
  font-family: 'Poppins', sans-serif;
  font-size: .78rem; font-weight: 600;
  color: #c85a30; text-decoration: none;
  padding: .2rem .6rem;
  border: 1px solid #c85a30; border-radius: 4px;
  transition: background .2s, color .2s;
}
.view-source:hover { background: #c85a30; color: #fff; }

/* Important note — amber accent */
.important-note { border-left-color: #e2b93b; }

/* Responsive: intro image shrinks on mobile */
@media (max-width: 600px) {
  .intro-card .intro-image { float: none; text-align: center; margin: 0 0 .75rem 0; width: 100%; }
  .intro-image img { width: 120px; }
}

/* ── Contact Page Styles (in global CSS so WP doesn't strip from content) ── */
.contact-page { max-width: 680px; margin: 0 auto; padding: 20px 20px 40px; }
.contact-heading { font-size: 2.2rem; color: #2e2a22; margin: 0 0 12px 0; font-weight: 700; text-align: center; }
.contact-intro { color: #4a5568; font-size: 1.05rem; line-height: 1.7; text-align: center; margin: 0 0 24px 0; }
.contact-intro a { color: #c85a30; text-decoration: none; font-weight: 600; }
.contact-intro a:hover { text-decoration: underline; }
.contact-form-card { background: #ffffff; border-radius: 12px; padding: 35px 30px; box-shadow: 0 4px 16px rgba(0,0,0,0.08); border: 1px solid #e2e8f0; }
.contact-form { display: flex; flex-direction: column; gap: 22px; }
.form-group { display: flex; flex-direction: column; }
.form-label { font-weight: 600; font-size: .92rem; color: #2d3748; margin-bottom: 8px; }
.form-label .required { color: #c85a30; margin-left: 2px; }
.form-input, .form-textarea { width: 100%; padding: 12px 15px; border: 2px solid #e2e8f0; border-radius: 8px; font-size: .95rem; font-family: inherit; background: #f7fafc; color: #2d3748; transition: border-color .2s, box-shadow .2s; box-sizing: border-box; }
.form-input:focus, .form-textarea:focus { outline: none; border-color: #c85a30; background: #fff; box-shadow: 0 0 0 3px rgba(200,90,48,.12); }
.form-input.error, .form-textarea.error { border-color: #c85a30; }
.form-textarea { min-height: 140px; resize: vertical; }
.form-error { display: none; color: #c85a30; font-size: .84rem; margin-top: 5px; font-weight: 500; }
.form-error.show { display: block; }
.form-submit-wrapper { text-align: center; margin-top: 8px; }
.form-submit { padding: 14px 40px; background: linear-gradient(135deg, #c85a30, #a84520); color: #fff; border: none; border-radius: 8px; font-weight: 600; font-size: 1rem; font-family: inherit; cursor: pointer; transition: transform .2s, box-shadow .2s; display: inline-flex; align-items: center; gap: 8px; }
.form-submit:hover:not(:disabled) { transform: translateY(-2px); box-shadow: 0 5px 15px rgba(200,90,48,.3); }
.form-submit:disabled { opacity: .7; cursor: not-allowed; }
.form-message { display: none; padding: 16px 20px; border-radius: 8px; margin-bottom: 22px; text-align: center; font-size: .95rem; line-height: 1.5; }
.form-message.success { background: #d4f4dd; border: 2px solid #48bb78; color: #22543d; }
.form-message.error-msg { background: #fde8e8; border: 2px solid #c85a30; color: #742a2a; }
.form-message.show { display: block; }
@media (min-width: 768px) {
  .contact-page { padding: 30px 20px 50px; }
  .contact-heading { font-size: 2.4rem; }
  .contact-form-card { padding: 40px 38px; }
}

/* ── Search Results ── */
.search-results-list { list-style: none; padding: 0; margin: 0; }
.search-results-list li { padding: 12px 0; border-bottom: 1px solid #e5e0d5; }
.search-results-list li a { color: #2e2a22; text-decoration: none; font-size: 1.05rem; font-weight: 600; }
.search-results-list li a:hover { color: #c85a30; }
.search-results-list li .search-excerpt { display: block; color: #6b7280; font-size: .9rem; margin-top: 4px; }
.search-results-list li .search-date { display: block; color: #9ca3af; font-size: .8rem; margin-top: 2px; }

/* ── Page heading: headline + subhead ── */
.page-subhead {
  font-family: 'Poppins', sans-serif !important;
  font-size: .78rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: .1em;
  color: #8a7a6a;
  margin: 0 0 .5rem;
  padding: 0;
}

/* ── Article category meta ── */
.article-meta {
  font-family: 'Poppins', sans-serif !important;
  font-size: .82rem;
  color: #8a7a6a;
  margin: 0 0 1.75rem;
  padding: 0;
}
.article-meta-label { font-weight: 600; color: #6b7280; }
.article-meta-value { color: #c85a30; text-decoration: none; font-weight: 600; }
.article-meta-value:hover { text-decoration: underline; }

/* ── Sponsor CTA Block ── */
.sponsor-cta { max-width: 750px; margin: 2rem auto; background: linear-gradient(135deg, #faf5ec 0%, #fff 100%); border: 2px solid #c85a30; border-radius: 12px; padding: 24px; position: relative; overflow: hidden; }
.sponsor-cta-badge { position: absolute; top: 0; right: 0; background: #c85a30; color: #fff; font-size: .7rem; font-weight: 600; padding: 4px 12px; border-radius: 0 0 0 8px; text-transform: uppercase; letter-spacing: .05em; }
.sponsor-cta-body { display: flex; align-items: center; justify-content: space-between; gap: 20px; flex-wrap: wrap; }
.sponsor-cta-text { flex: 1; min-width: 200px; }
.sponsor-cta-text strong { display: block; font-size: 1.05rem; color: #2e2a22; margin-bottom: 4px; }
.sponsor-cta-text span { font-size: .9rem; color: #6b7280; }
.sponsor-cta-btn { display: inline-block; padding: 12px 28px; background: #c85a30; color: #fff !important; text-decoration: none !important; border-radius: 8px; font-weight: 600; font-size: .95rem; white-space: nowrap; transition: background .2s, transform .2s; }
.sponsor-cta-btn:hover { background: #a84520; transform: translateY(-1px); }
@media (max-width: 600px) {
  .sponsor-cta-body { flex-direction: column; text-align: center; }
  .sponsor-cta-btn { width: 100%; text-align: center; }
}

/* Responsive footer */
@media (max-width: 600px) {
  .pd-footer-inner { grid-template-columns: 1fr; }
  .pd-header-inner { padding: .6rem 1rem; gap: .75rem; }
  .pd-header .wp-block-navigation-item a { padding: .4rem .5rem; font-size: .82rem; }
  .pd-header .wp-block-search__input { min-width: 120px; }
}
</style>
<!-- /wp:html -->

<!-- wp:group {"className":"pd-header","style":{"spacing":{"padding":{"top":"0","bottom":"0","left":"0","right":"0"}},"color":{"background":"#2e2a22"}},"layout":{"type":"constrained","contentSize":"100%"}} -->
<div class="wp-block-group pd-header has-background" style="background-color:#2e2a22;padding-top:0;padding-right:0;padding-bottom:0;padding-left:0"><!-- wp:group {"className":"pd-header-inner","layout":{"type":"flex","flexWrap":"nowrap","justifyContent":"space-between","verticalAlignment":"center"}} -->
<div class="wp-block-group pd-header-inner"><!-- wp:html -->
<a href="/" class="pd-logo" aria-label="pep-dose home"><span class="pd-logo-pep">pep</span><span class="pd-logo-sep">·</span><span class="pd-logo-dose">dose</span></a>
<!-- /wp:html -->

<!-- wp:navigation {"ref":5,"style":{"spacing":{"blockGap":"0px"}},"layout":{"type":"flex","justifyContent":"right","flexWrap":"nowrap"}} /-->

<!-- wp:search {"label":"Search","showLabel":false,"placeholder":"search pep-dose","width":160,"widthUnit":"px","buttonPosition":"no-button","fontSize":"small"} /--></div>
<!-- /wp:group --></div>
<!-- /wp:group -->'''

print('Updating header template part...')
result = wp_request('template-parts/blank-canvas-3%2F%2Fheader', method='POST',
                    data={'content': HEADER_CONTENT})
if result:
    print('  ✓ Header updated')
else:
    print('  ✗ Header update failed')


# ── Search results template — JS-powered via WP REST API ───────────────────
# WP.com Personal plan doesn't server-render dynamic blocks (wp:post-title,
# wp:post-excerpt) inside FSE query loops in search templates, so we use
# JavaScript to fetch results from the public WP REST API instead.
SEARCH_TEMPLATE = r'''<!-- wp:template-part {"slug":"header","tagName":"header","theme":"blank-canvas-3"} /-->

<!-- wp:html -->
<main style="max-width:800px;margin:0 auto;padding:2rem 1.5rem 3rem">
<h1 id="pd-search-heading" style="font-family:Poppins,sans-serif;font-size:1.8rem;color:#2e2a22;margin:0 0 1.5rem"></h1>
<div id="pd-search-results"></div>
<script>
(function(){
  var params = new URLSearchParams(window.location.search);
  var q = (params.get('s') || '').trim();
  var heading = document.getElementById('pd-search-heading');
  var container = document.getElementById('pd-search-results');
  heading.textContent = q ? 'Search results for \u201c' + q + '\u201d' : 'Search';
  if (!q) {
    container.innerHTML = '<p style="color:#6b7280;font-family:Poppins,sans-serif">Enter a search term above.</p>';
    return;
  }
  container.innerHTML = '<p style="color:#6b7280;font-family:Poppins,sans-serif">Searching\u2026</p>';
  var url = '/wp-json/wp/v2/search?search=' + encodeURIComponent(q) + '&per_page=20&subtype=any';
  fetch(url)
    .then(function(r){ return r.json(); })
    .then(function(results){
      if (!Array.isArray(results) || !results.length) {
        container.innerHTML = '<p style="color:#6b7280;font-family:Poppins,sans-serif">No results found for \u201c' + q + '\u201d. Try browsing <a href="/articles/" style="color:#c85a30">Education &amp; Articles</a> or <a href="/dosages-and-protocols/" style="color:#c85a30">Dosages &amp; Protocols</a>.</p>';
        return;
      }
      var BADGE = {
        protocol: {text:'Protocol', bg:'#3aaa8c'},
        article:  {text:'Article',  bg:'#c48630'}
      };
      function badge(item) {
        var u = item.url;
        if (u.indexOf('dosage-protocol') !== -1 ||
            u.indexOf('/single-peptide-dosages/') !== -1 ||
            u.indexOf('/peptide-blend-dosages/')  !== -1 ||
            u.indexOf('/peptide-stack-dosages/')  !== -1) return BADGE.protocol;
        if (u.indexOf('/what-is-') !== -1 || u.indexOf('/what-are-') !== -1 ||
            u.indexOf('retatrutide-vs-') !== -1 ||
            u.indexOf('-reconstitution-') !== -1) return BADGE.article;
        return null;
      }
      var PILL = 'display:inline-block;font-family:Poppins,sans-serif;font-size:.72rem;font-weight:600;letter-spacing:.04em;text-transform:uppercase;color:#fff;padding:2px 8px;border-radius:20px;margin-top:5px;';
      var html = '';
      results.forEach(function(item){
        var b = badge(item);
        html += '<div style="padding:14px 0;border-bottom:1px solid #e5e0d5">';
        html += '<a href="' + item.url + '" style="color:#2e2a22;text-decoration:none;font-size:1.05rem;font-weight:600;font-family:Poppins,sans-serif;line-height:1.4">' + item.title + '</a>';
        if (b) html += '<br><span style="' + PILL + 'background:' + b.bg + '">' + b.text + '</span>';
        html += '</div>';
      });
      container.innerHTML = html;
    })
    .catch(function(){
      container.innerHTML = '<p style="color:#c85a30;font-family:Poppins,sans-serif">Search unavailable. Try again shortly.</p>';
    });
})();
</script>
</main>
<!-- /wp:html -->

<!-- wp:template-part {"slug":"footer","tagName":"footer","theme":"blank-canvas-3"} /-->'''

print('\nCreating/updating search template...')
# Try to update existing search template first, then create if it doesn't exist
result = wp_request('templates/blank-canvas-3%2F%2Fsearch', method='POST',
                    data={'content': SEARCH_TEMPLATE})
if result:
    print('  ✓ Search template updated')
else:
    print('  Trying to create search template...')
    result = wp_request('templates', method='POST',
                        data={'slug': 'search',
                              'theme': 'blank-canvas-3',
                              'content': SEARCH_TEMPLATE,
                              'title': 'Search Results',
                              'status': 'publish'})
    if result:
        print('  ✓ Search template created')
    else:
        print('  ✗ Search template creation failed')


# ── Single post template — clean article layout, no date/author ──────────────
# Removes the theme's default date, author, and title header so our embedded
# H1/subhead/category-meta in the post content controls the full layout.
SINGLE_TEMPLATE = r'''<!-- wp:template-part {"slug":"header","tagName":"header","theme":"blank-canvas-3"} /-->

<!-- wp:group {"tagName":"main","style":{"spacing":{"padding":{"top":"2rem","bottom":"3rem","left":"1.5rem","right":"1.5rem"}}},"layout":{"type":"constrained","contentSize":"860px"}} -->
<main class="wp-block-group" style="padding-top:2rem;padding-bottom:3rem;padding-left:1.5rem;padding-right:1.5rem">
<!-- wp:post-content {"layout":{"type":"constrained","contentSize":"860px"}} /-->
</main>
<!-- /wp:group -->

<!-- wp:template-part {"slug":"footer","tagName":"footer","theme":"blank-canvas-3"} /-->'''

print('\nUpdating single post template...')
result = wp_request('templates/blank-canvas-3%2F%2Fsingle', method='POST',
                    data={'content': SINGLE_TEMPLATE})
if result:
    print('  ✓ Single post template updated')
else:
    print('  Trying to create single post template...')
    result = wp_request('templates', method='POST',
                        data={'slug': 'single',
                              'theme': 'blank-canvas-3',
                              'content': SINGLE_TEMPLATE,
                              'title': 'Single Post',
                              'status': 'publish'})
    if result:
        print('  ✓ Single post template created')
    else:
        print('  ✗ Single post template failed')
