# pep-dose.com

Peptide dosage educational site. Static build deployed to WordPress.com.

## Build
- `python3 build.py` — rebuilds static site from templates and config
- Config: `_theme/config.json` — all site settings, colors, nav, WP identifiers

## Architecture
- WordPress.com (blog_id: 253153078, theme: pub/blank-canvas-3)
- GitHub Pages hosts calculator widget (WP Personal plan strips <script>/<input>)
- Calculator gateway page on WP links to: https://xwrvnggp9n-star.github.io/pepdose-site/calculator-widget.html

## Branding — Warm Slate Palette
- Primary dark: #2e2a22 | Accent: #c85a30 | Teal: #3aaa8c
- Body bg: #faf5ec | Body text: #2b2318 | Header text: #fdf8f0
- Logo: CSS text "pep·dose" (pep=teal, ·=red, dose=white)
- Fonts: Poppins (headings), Lora (body)

## Conventions
- Colors injected via <style> in WP header template part (overrides CDN global styles)
- Author displays as "Pep-Dose Staff" with mailto:info@pep-dose.com
- Always create content as draft unless explicitly asked to publish
