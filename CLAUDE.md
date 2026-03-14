# pep-dose.com

Peptide dosage educational site deployed to WordPress.com.

## Build & Deploy
- `python3 build.py` — extracts and cleans article content from WP export HTML files → `_dist/`
- `python3 deploy.py` — pushes cleaned content from `_dist/` to WordPress.com via REST API
- `python3 deploy.py --dry-run` — preview what would be deployed
- `python3 deploy.py <slug>` — deploy a single page/post by slug
- Config: `_theme/config.json` — colors, sponsor links, WP identifiers
- Credentials: `.env` file (gitignored) with WP_SITE, WP_USER, WP_APP_PASSWORD
- "Deploy to production" means: `git push` to GitHub AND `python3 deploy.py` to WordPress.com
- Always rebuild (`python3 build.py`) before deploying — deploy.py reads from `_dist/`

## Architecture
- WordPress.com handles ALL rendering: header, footer, nav, CSS, fonts (via template parts)
- `build.py` only extracts article body content from source HTML exports and cleans it
- `_dist/` files contain raw article HTML — no `<head>`, header, or footer wrapping
- `deploy.py` reads `_dist/` files directly and pushes content to WP REST API
- GitHub Pages hosts calculator widget (WP Personal plan strips `<script>`/`<input>`)
- Calculator gateway page on WP links to GitHub Pages hosted widget
- WP blog_id: 253153078, theme: pub/blank-canvas-3

## Build Pipeline
- Source HTML files are full WP exports; `build.py` extracts article content from `<main>`/`<article>`
- Many source files lack `</main>` — build.py grabs to EOF then strips embedded old footers/JS
- Content transforms: color replacement, URL fixing, PureLab removal, sponsor injection, lazy loading
- `deploy.py` has SLUG_ALIASES for WP slugs that differ from source dir names (e.g. `-2` suffixes)
- `calculator-widget.html` is copied directly, not processed through the pipeline

## Sponsorship
- Current sponsor: White Market Peptides (WMP) — whitemarketpeptides.com
- Coupon code: PEPDOSE (10% off)
- `_theme/config.json` → `sponsor_links` maps page slugs to WMP product paths
- All WMP links get UTM tags via `sponsor_url_for_slug()` in build.py
- Zero references to PureLab Peptides or peptidedosages.com allowed anywhere

## Branding — Warm Slate Palette
- Primary dark: #2e2a22 | Accent: #c85a30 | Teal: #3aaa8c
- Body bg: #faf5ec | Body text: #2b2318 | Header text: #fdf8f0
- Logo: CSS text "pep·dose" (pep=teal, ·=red, dose=white)
- Fonts: Poppins (headings), Lora (body)

## Conventions
- Colors/fonts managed via WP header template part `<style>` block (not local CSS files)
- Author displays as "Pep-Dose Staff" with mailto:info@pep-dose.com
- Always create content as draft unless explicitly asked to publish
- Use `&` not "and" in nav/footer titles (e.g. "Dosages & Protocols")
- Sponsor CTA blocks use `font-family: inherit` (not system sans-serif)
- No local preview server — preview changes on the live WP site after deploying
