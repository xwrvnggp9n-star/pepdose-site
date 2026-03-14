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

/* ── Contact Page Styles (in global CSS so WP doesn't strip from content) ── */
.contact-page { max-width: 680px; margin: 0 auto; padding: 60px 20px 80px; }
.contact-heading { font-size: 2.2rem; color: #2e2a22; margin: 0 0 20px 0; font-weight: 700; text-align: center; }
.contact-intro { color: #4a5568; font-size: 1.05rem; line-height: 1.7; text-align: center; margin: 0 0 40px 0; }
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
  .contact-page { padding: 80px 20px 100px; }
  .contact-heading { font-size: 2.6rem; }
  .contact-form-card { padding: 40px 38px; }
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
