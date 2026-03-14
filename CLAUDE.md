# pep-dose.com

Peptide dosage educational site. Static build deployed to WordPress.com.

## Build & Deploy
- `python3 build.py` — rebuilds static site from templates and config
- `python3 deploy.py` — deploys built content to WordPress.com via REST API
- `python3 deploy.py --dry-run` — preview what would be deployed
- `python3 deploy.py <slug>` — deploy a single page/post by slug
- Config: `_theme/config.json` — all site settings, colors, nav, WP identifiers
- Credentials: `.env` file (gitignored) with WP_SITE, WP_USER, WP_APP_PASSWORD
- "Deploy to production" means: `git push` to GitHub AND `python3 deploy.py` to WordPress.com
- Local preview: `python3 _theme/serve.py` — serves `_dist/` with clean URL support
- Always rebuild (`python3 build.py`) before deploying — deploy.py reads from `_dist/`

## Architecture
- WordPress.com (blog_id: 253153078, theme: pub/blank-canvas-3)
- GitHub Pages hosts calculator widget (WP Personal plan strips <script>/<input>)
- Calculator gateway page on WP links to: https://xwrvnggp9n-star.github.io/pepdose-site/calculator-widget.html

## Build Pipeline Gotchas
- Source HTML files are full WP exports; `build.py` extracts `<head>` and `<main>` independently
- Many source files lack `</main>` — build.py grabs to EOF then strips embedded old footers/JS
- Schema JSON-LD is processed separately from main_html — transformations must apply to both
- `deploy.py` extracts `<article>` content from `_dist/` files (WP stores article body only)
- `deploy.py` has SLUG_ALIASES for WP slugs that differ from source dir names (e.g. `-2` suffixes)
- `calculator-widget.html` is copied directly, not processed through build pipeline

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
- Colors injected via <style> in WP header template part (overrides CDN global styles)
- Author displays as "Pep-Dose Staff" with mailto:info@pep-dose.com
- Always create content as draft unless explicitly asked to publish
- Use `&` not "and" in nav/footer titles (e.g. "Dosages & Protocols")
- Sponsor CTA blocks use `font-family: inherit` (not system sans-serif)
