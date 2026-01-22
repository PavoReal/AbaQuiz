# abaquiz landing page - implementation plan

## overview

ultra minimal, single-page landing for abaquiz. dark mode, ibm plex mono font, all lowercase. static html with tailwind cdn.

---

## design spec

**tagline:** "daily doses, lasting confidence"

**copy:**
```
abaquiz

daily doses, lasting confidence

daily bcba exam questions delivered straight to telegram.
build the habit. pass the exam.

[beta]

[ join on telegram → ]

new questions added every week
```

**colors:**
- background: `#05181e` (dark-teal-950)
- primary text: `#d4eef7` (dark-teal-100)
- muted text: `#176782` (dark-teal-700)
- accent/cta: `#04defb` (teal-500)
- cta hover: `#36e5fc` (teal-400)
- beta badge: `#26f00f` (frosted-mint-500) with `#052202` (frosted-mint-950) bg

**typography:**
- font: ibm plex mono (google fonts)
- all lowercase
- logo: 2.5-3rem, bold
- tagline: 1.25rem
- body: 1rem
- fine print: 0.875rem

**layout:**
- centered vertically and horizontally
- max-width ~600px for content
- generous padding (4-6rem vertical on desktop)
- mobile responsive

---

## file structure

```
landing/
├── index.html          # single page, all content
├── favicon.svg         # simple text-based favicon (optional)
└── PLAN.md             # this file
```

no build step. tailwind via cdn. custom colors via inline style block.

---

## implementation steps

### step 1: create index.html

- [ ] html boilerplate with proper meta tags
- [ ] google fonts import (ibm plex mono)
- [ ] tailwind cdn script
- [ ] custom color css variables in `<style>` block
- [ ] main content structure

### step 2: build the layout

- [ ] full-height centered container
- [ ] logo text "abaquiz"
- [ ] tagline "daily doses, lasting confidence"
- [ ] description paragraph
- [ ] beta badge pill
- [ ] telegram cta button
- [ ] footer note "new questions added every week"

### step 3: styling details

- [ ] apply dark background
- [ ] typography sizing and spacing
- [ ] cta button with hover state
- [ ] beta badge styling
- [ ] mobile responsive adjustments
- [ ] subtle fade-in animation (optional, css only)

### step 4: final touches

- [ ] meta tags (og:title, og:description, twitter card)
- [ ] favicon
- [ ] test on mobile viewport
- [ ] validate html

---

## deployment (cloudflare pages)

1. connect repo to cloudflare pages
2. set build output directory: `landing`
3. no build command needed (static files)
4. set custom domain if desired

---

## tech decisions

| choice | reason |
|--------|--------|
| tailwind cdn | no build step, perfect for single static page |
| no alpine/htmx | page is too simple, no interactivity needed |
| inline styles for colors | avoids extra css file, keeps it self-contained |
| google fonts cdn | simplest way to load ibm plex mono |

---

## future considerations (out of scope)

- email signup for launch notifications
- analytics (plausible/fathom)
- testimonials section
- faq accordion
- dark/light mode toggle
