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
- Content transforms: color replacement, URL fixing, PureLab removal, sponsor injection, lazy loading, structured data
- `deploy.py` has SLUG_ALIASES for WP slugs that differ from source dir names (e.g. `-2` suffixes)
- `calculator-widget.html` is copied directly, not processed through the pipeline

## Templates & Global CSS
- `python3 update_wp_templates.py` — pushes header template part (global CSS) and search template to WP.com
- Search template: `blank-canvas-3//search` — uses `postType: "any"` to return both posts and pages
- WP settings changed via REST API: `posts_per_page: 50`, `page_for_posts: 0`

## Calculator (GitHub Pages)
- `calculator-widget.html` deployed to GitHub Pages via `git push` (not deploy.py)
- `PDC_PROTOCOLS` array defines peptide dropdown entries (name, vial, water, group)
- Blends & Stacks optgroup listed FIRST in dropdown — macOS native `<select>` cuts off long lists
- Dropdown selector: `optgroup[label="Blends & Stacks"]` and `optgroup[label="Single Peptides"]`

## Structured Data (Schema.org)
- Uses Microdata format (HTML attributes: itemscope/itemtype/itemprop) — NOT JSON-LD (WP.com strips `<script>`)
- HowTo schema on dosage protocol pages (reconstitution steps in `<ol>`)
- FAQPage schema on education articles (Q&A sections — supports `Q1:` and `<h3>question</h3>` formats)
- Injected by `build.py` during content transforms (`inject_howto_schema()`, `inject_faq_schema()`)

## SEO
- Google Search Console: property verified as `sc-domain:pep-dose.com` (logged in as sandy@whitemarketpeptides.com)
- Sitemaps auto-managed by WordPress.com (`sitemap.xml` → `sitemap-1.xml`)
- `deploy.py` pushes SEO meta descriptions via `excerpt` + `advanced_seo_description` fields
- Custom descriptions in `_SEO_DESCRIPTIONS` dict; fallback: auto-generated from content
- WP.com REST API does NOT expose `permalink_structure` — cannot change via API
- WP.com wp-admin `/options-permalink.php` returns "permission denied" — permalink changes may require WP.com support
- Posts use date-based URLs (`/%year%/%monthnum%/%day%/%postname%/`); pages use clean slugs

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

## New Content Checklist
When adding a new peptide or protocol to the site, ALL of the following must be updated:

### Adding a New Dosage Protocol Page
1. **Source HTML** — Create `single-peptide-dosages/<slug>/index.html` (or `peptide-blend-dosages/` for blends)
2. **Calculator dropdown** — Add entry to `PDC_PROTOCOLS` array in `calculator-widget.html` (name, vial size, water volume, group)
3. **Sponsor link** — Add slug → WMP product URL mapping in `_theme/config.json` → `sponsor_links`
4. **Cross-links in build.py**:
   - Add to `_DOSAGE_RELATED` dict (maps peptide keywords → education article links shown on protocol pages)
   - Update `_ARTICLE_RELATED` dict entries for related education articles to link back to new protocol
5. **Rebuild & deploy** — `python3 build.py && python3 deploy.py <slug>` + `git push` (pushes calculator to GitHub Pages)

### Adding a New Education Article
1. **Source HTML** — Create `<slug>/index.html` with article content
2. **Article categories** — Add slug to appropriate category in `_ARTICLE_CATEGORIES` list in `build.py`
3. **Cross-links in build.py**:
   - Add entry to `_ARTICLE_RELATED` dict (maps slug → list of related articles + protocol links)
   - Update related articles' `_ARTICLE_RELATED` entries to link back to new article
4. **Sponsor link** — Add slug → WMP product URL mapping in `_theme/config.json` → `sponsor_links` (if WMP sells this peptide)
5. **Rebuild & deploy** — `python3 build.py && python3 deploy.py <slug>` + `git push`

### Key Files That Must Stay in Sync
| What | File | Section/Variable |
|------|------|-----------------|
| Calculator peptide list | `calculator-widget.html` | `PDC_PROTOCOLS` array |
| Sponsor product links | `_theme/config.json` | `sponsor_links` object |
| Protocol cross-links | `build.py` | `_DOSAGE_RELATED` dict |
| Article cross-links | `build.py` | `_ARTICLE_RELATED` dict |
| Article categories | `build.py` | `_ARTICLE_CATEGORIES` list |
| WP slug aliases | `deploy.py` | `SLUG_ALIASES` dict |
| Dosages catalog page | auto-generated | `build_dosages_page()` reads dirs |
| Articles catalog page | auto-generated | `build_blog_page()` reads `_ARTICLE_CATEGORIES` |

### Verification After Any Content Change
- `python3 build.py` completes without errors
- `python3 tests.py` passes all tests
- Every protocol page has: sponsor CTA block, Related Reading section, calculator link
- Every article page has: sponsor CTA block, Related Reading section, calculator link
- Dosage pages have HowTo schema (verify `itemtype="https://schema.org/HowTo"` in `_dist/` output)
- Article pages with FAQ sections have FAQPage schema (verify `itemtype="https://schema.org/FAQPage"`)
- Calculator dropdown includes all protocol vial sizes
- Dosages & Protocols catalog page lists the new protocol
- Education & Articles catalog page lists the new article in correct category
