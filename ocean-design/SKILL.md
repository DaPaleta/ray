---
name: ocean-design
description: Design system skill for ocean. Activate when building UI components, pages, or any visual elements. Provides exact color tokens, typography scale, spacing grid, component patterns, and craft rules. Read references/DESIGN.md before writing any CSS or JSX.
---

# ocean Design System

You are building UI for **ocean**. Light-themed, cool palette, sans-serif typography (Rethink Sans), compact density on a 4px grid.

## Visual Reference

**IMPORTANT**: Study ALL screenshots below before writing any UI. Match colors, typography, spacing, layout, and motion exactly as shown.

### Homepage

![ocean Homepage](screenshots/homepage.png)

> Read `references/DESIGN.md` for full token details.

## Design Philosophy

- **Layered depth** — use shadow tokens to create a sense of physical layering. Each elevation level has a specific shadow.
- **Gradient accents** — gradients are used thoughtfully for emphasis, not decoration.
- **Type pairing** — Rethink Sans for body/UI text, DM Sans for headings/display. Never introduce a third typeface.
- **compact density** — 4px base grid. Every dimension is a multiple of 4.
- **cool palette** — the color temperature runs cool, matching the sans-serif typography.
- **Restrained accent** — `#99eeff` is the only pop of color. Used exclusively for CTAs, links, focus rings, and active states.
- **Subtle motion** — transitions smooth state changes. Keep durations under 300ms, use ease-out curves.

## Color System

### Core Palette

| Role | Token | Hex | Use |
|------|-------|-----|-----|
| Background | `--background` | `#ffffff` | Page/app background |
| Surface | `--surface` | `#eceff4` | Cards, panels, modals |
| Text Primary | `--text-primary` | `#002231` | Headings, body text |
| Text Muted | `--text-muted` | `#bababa` | Captions, placeholders |
| Accent | `--accent` | `#99eeff` | CTAs, links, focus rings |
| Border | `--border` | `#1e1f21` | Dividers, card borders |

### Status Colors

| Status | Hex | Use |
|--------|-----|-----|
| Warning | `#ffc375` | Caution states, pending items |
| Danger | `#eb8f49` | Errors, destructive actions |

### Extended Palette

- **framer-text-color:** `#000000` — Deep background layer or shadow color
- **border-color:** `#c1d3d8`
- `#d2dbe5`
- **framer-link-text-color:** `#0099ff`
- `#00141a` — Deep background layer or shadow color
- `#00313c` — Deep background layer or shadow color
- `#a3a3a3`
- `#12111c` — Deep background layer or shadow color

### CSS Variable Tokens

```css
--border-bottom-width: 1px;
--border-left-width: 1px;
--border-right-width: 1px;
--border-style: solid;
--border-top-width: 1px;
--framer-text-background-color: initial;
--framer-text-background-radius: initial;
--framer-text-background-corner-shape: initial;
--framer-text-background-padding: initial;
--border-bottom-width: .5px;
--border-left-width: .5px;
--border-right-width: .5px;
--border-style: solid;
--border-top-width: .5px;
--framer-input-background: #00243005;
--framer-input-border-bottom-width: 1px;
--framer-input-border-color: #0024308c;
--framer-input-border-left-width: 1px;
--framer-input-border-radius-bottom-left: 10px;
--framer-input-border-radius-bottom-right: 10px;
```

## Typography

### Font Stack

- **Rethink Sans** — Heading 1, Heading 2, Heading 3
- **DM Sans** — Body, Caption
- **Fragment Mono** — Code

### Font Sources

```css
@font-face {
  font-family: "DM Sans";
  src: url("fonts/DMSans-Bold.ttf") format("truetype");
  font-weight: 700;
}
@font-face {
  font-family: "DM Sans";
  src: url("fonts/DMSans-Regular.ttf") format("truetype");
  font-weight: 400;
}
@font-face {
  font-family: "Rethink Sans";
  src: url("fonts/RethinkSans-Bold.ttf") format("truetype");
  font-weight: 700;
}
@font-face {
  font-family: "Rethink Sans";
  src: url("fonts/RethinkSans-Regular.ttf") format("truetype");
  font-weight: 400;
}
@font-face {
  font-family: "Roboto";
  src: url("fonts/Roboto-Bold.ttf") format("truetype");
  font-weight: 700;
}
@font-face {
  font-family: "Roboto";
  src: url("fonts/Roboto-Regular.ttf") format("truetype");
  font-weight: 400;
}
@font-face {
  font-family: "Fragment Mono";
  src: url("fonts/FragmentMono-Regular.ttf") format("truetype");
  font-weight: 400;
}
@font-face {
  font-family: "Gloock";
  src: url("fonts/Gloock-Regular.ttf") format("truetype");
  font-weight: 400;
}
@font-face {
  font-family: "Inter";
  src: url("fonts/Inter-Bold.ttf") format("truetype");
  font-weight: 700;
}
@font-face {
  font-family: "Inter";
  src: url("fonts/Inter-Regular.ttf") format("truetype");
  font-weight: 400;
}
@font-face {
  font-family: "Satoshi";
  src: url("fonts/Satoshi-700.woff2") format("woff2");
  font-weight: 700;
}
@font-face {
  font-family: "Satoshi";
  src: url("fonts/Satoshi-Regular.woff2") format("woff2");
  font-weight: 400;
}
@font-face {
  font-family: "Manrope";
  src: url("fonts/Manrope-Bold.ttf") format("truetype");
  font-weight: 700;
}
@font-face {
  font-family: "Manrope";
  src: url("fonts/Manrope-Regular.ttf") format("truetype");
  font-weight: 400;
}
```

### Type Scale

| Role | Family | Size | Weight |
|------|--------|------|--------|
| Heading 1 | Rethink Sans | calc(var(--framer-blockquote-font-size,var(--framer-font-size,16px))*var(--framer-font-size-scale,1)) | 700 |
| Heading 2 | Rethink Sans | calc(var(--framer-link-hover-font-size,var(--framer-blockquote-font-size,var(--framer-font-size,16px)))*var(--framer-font-size-scale,1)) | 700 |
| Heading 3 | Rethink Sans | calc(var(--framer-link-current-font-size,var(--framer-link-font-size,var(--framer-font-size,16px)))*var(--framer-font-size-scale,1)) | 700 |
| Body | DM Sans | calc(var(--framer-link-hover-font-size,var(--framer-link-current-font-size,var(--framer-link-font-size,var(--framer-font-size,16px))))*var(--framer-font-size-scale,1)) | 400 |
| Caption | DM Sans | var(--framer-font-size,16px) | 400 |
| Code | Fragment Mono | 14px | 400 |

### Typography Rules

- Body/UI: **Rethink Sans**, Headings: **DM Sans** — these are the only display fonts
- Max 3-4 font sizes per screen
- Headings: weight 600-700, body: weight 400
- Use color and opacity for text hierarchy, not additional font sizes
- Line height: 1.5 for body, 1.2 for headings

## Spacing & Layout

### Base Grid: 4px

Every dimension (margin, padding, gap, width, height) must be a multiple of **4px**.

### Spacing Scale

`2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22, 24` px

### Spacing as Meaning

| Spacing | Use |
|---------|-----|
| 4-8px | Tight: related items (icon + label, avatar + name) |
| 12-16px | Medium: between groups within a section |
| 24-32px | Wide: between distinct sections |
| 48px+ | Vast: major page section breaks |

### Border Radius

Scale: `5px, 6px, 8px, 11px, 20px, 30px, 40px, 100%, 140px, 180px, 470px, 500px, inherit`
Default: `40px`

### Container

Max-width: `1199px`, centered with auto margins.

### Breakpoints

| Name | Value |
|------|-------|
| lg | 809px |
| lg | 809.98px |
| lg | 810px |
| xl | 1199px |
| xl | 1199.98px |
| xl | 1200px |
| 2xl | 1326px |
| 2xl | 1326.98px |
| 2xl | 1327px |

Mobile-first: design for small screens, layer on responsive overrides.

## Component Patterns

### Card

```css
.card {
  background: #eceff4;
  border: 1px solid #1e1f21;
  border-radius: 40px;
  padding: 16px;
  box-shadow: unset;
}
```

```html
<div class="card">
  <h3>Card Title</h3>
  <p>Card content goes here.</p>
</div>
```

### Button

```css
/* Primary */
.btn-primary {
  background: #99eeff;
  color: #002231;
  border-radius: 40px;
  padding: 8px 16px;
  font-weight: 500;
  transition: opacity 150ms ease;
}
.btn-primary:hover { opacity: 0.9; }

/* Ghost */
.btn-ghost {
  background: transparent;
  border: 1px solid #1e1f21;
  color: #002231;
  border-radius: 40px;
  padding: 8px 16px;
}
```

```html
<button class="btn-primary">Get Started</button>
<button class="btn-ghost">Learn More</button>
```

### Input

```css
.input {
  background: #ffffff;
  border: 1px solid #1e1f21;
  border-radius: 40px;
  padding: 8px 12px;
  color: #002231;
  font-size: 14px;
}
.input:focus { border-color: #99eeff; outline: none; }
```

```html
<input class="input" type="text" placeholder="Search..." />
```

### Badge / Chip

```css
.badge {
  display: inline-flex;
  align-items: center;
  padding: 4px 8px;
  border-radius: 9999px;
  font-size: 12px;
  font-weight: 500;
  background: #eceff4;
  color: #bababa;
}
```

```html
<span class="badge">New</span>
<span class="badge">Beta</span>
```

### Modal / Dialog

```css
.modal-backdrop { background: rgba(0, 0, 0, 0.6); }
.modal {
  background: #eceff4;
  border: 1px solid #1e1f21;
  border-radius: inherit;
  padding: 24px;
  max-width: 480px;
  width: 90vw;
  box-shadow: inset .557334px .358286px 1.45764px -1.125px #ffffff38,inset 1.69015px 1.08653px 4.42039px -2.25px #fff3,inset 4.46786px 2.87219px 11.6851px -3.375px #ffffff29,inset 14px 9px 36.6153px -4.5px #ffffff05;
}
```

```html
<div class="modal-backdrop">
  <div class="modal">
    <h2>Dialog Title</h2>
    <p>Dialog content.</p>
    <button class="btn-primary">Confirm</button>
    <button class="btn-ghost">Cancel</button>
  </div>
</div>
```

### Table

```css
.table { width: 100%; border-collapse: collapse; }
.table th {
  text-align: left;
  padding: 8px 12px;
  font-weight: 500;
  font-size: 12px;
  color: #bababa;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  border-bottom: 1px solid #1e1f21;
}
.table td {
  padding: 12px;
  border-bottom: 1px solid #1e1f21;
}
```

```html
<table class="table">
  <thead><tr><th>Name</th><th>Status</th><th>Date</th></tr></thead>
  <tbody>
    <tr><td>Item One</td><td>Active</td><td>Jan 1</td></tr>
    <tr><td>Item Two</td><td>Pending</td><td>Jan 2</td></tr>
  </tbody>
</table>
```

### Navigation

```css
.nav {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  border-bottom: 1px solid #1e1f21;
}
.nav-link {
  color: #bababa;
  padding: 8px 12px;
  border-radius: 40px;
  transition: color 150ms;
}
.nav-link:hover { color: #002231; }
.nav-link.active { color: #99eeff; }
```

```html
<nav class="nav">
  <a href="/" class="nav-link active">Home</a>
  <a href="/about" class="nav-link">About</a>
  <a href="/pricing" class="nav-link">Pricing</a>
  <button class="btn-primary" style="margin-left: auto">Get Started</button>
</nav>
```

### Extracted Components

These components were found in the codebase:

**Button** (`html`)

**Footer** (`html`)

## Page Structure

The following page sections were detected:

- **Hero** — Hero section (detected from heading structure)
- **Footer** — Page footer with links and info (24 items)

When building pages, follow this section order and structure.

## Animation & Motion

This project uses **subtle motion**. Transitions smooth state changes without calling attention.

### Motion Tokens

- **Duration scale:** `150ms`

### Motion Guidelines

- **Duration:** Use values from the duration scale above. Short (150ms) for micro-interactions, long (150ms) for page transitions
- **Easing:** `ease-out` for enters, `ease-in` for exits
- **Direction:** Elements enter from bottom/right, exit to top/left
- **Reduced motion:** Always respect `prefers-reduced-motion` — disable animations when set

## Depth & Elevation

### Shadow Tokens

- Raised (cards, buttons): `unset`
- Raised (cards, buttons): `var(--framer-input-box-shadow)`
- Raised (cards, buttons): `var(--framer-input-focused-box-shadow,var(--framer-input-box-shadow))`
- Overlay (modals, dialogs): `inset .557334px .358286px 1.45764px -1.125px #ffffff38,inset 1.69015px 1.08653px 4.42039px -2.25px #fff3,inset 4.46786px 2.87219px 11.6851px -3.375px #ffffff29,inset 14px 9px 36.6153px -4.5px #ffffff05`
- Overlay (modals, dialogs): `inset .906987px .151164px 2.02289px -.5625px #ffffff08,inset 2.14972px .358286px 4.79462px -1.125px #ffffff08,inset 3.92131px .653551px 8.74587px -1.6875px #ffffff08,inset 6.51917px 1.08653px 14.54px -2.25px #ffffff05,inset 10.5279px 1.75465px 23.4809px -2.8125px #ffffff05,inset 17.2332px 2.87219px 38.4359px -3.375px #ffffff05,inset 29.6743px 4.94572px 66.1841px -3.9375px #ffffff03,inset 54px 9px 120.439px -4.5px #fff0`
- Overlay (modals, dialogs): `10px 11px 32px -20px #00000040`

### Z-Index Scale

`0, 1, 2, 3, 4, 5, 10`

Use these exact values — never invent z-index values.

## Anti-Patterns (Never Do)

- **No blur effects** — no backdrop-blur, no filter: blur()
- **No zebra striping** — tables and lists use borders for separation
- **No invented colors** — every hex value must come from the palette above
- **No arbitrary spacing** — every dimension is a multiple of 4px
- **No extra fonts** — only Rethink Sans and DM Sans and Fragment Mono are allowed
- **No arbitrary border-radius** — use the scale: 5px, 6px, 8px, 11px, 20px, 30px, 40px, 140px, 180px, 470px
- **No opacity for disabled states** — use muted colors instead
- **No pill shapes** — this design doesn't use rounded-full / 9999px radius

## Workflow

1. **Read** `references/DESIGN.md` before writing any UI code
2. **Pick colors** from the Color System section — never invent new ones
3. **Set typography** — Rethink Sans, DM Sans, Fragment Mono only, using the type scale
4. **Build layout** on the 4px grid — check every margin, padding, gap
5. **Match components** to patterns above before creating new ones
6. **Apply elevation** — use shadow tokens
7. **Validate** — every value traces back to a design token. No magic numbers.

## Brand Spec

- **Favicon:** `https://framerusercontent.com/images/Urq1t3rfnGs74JTdrcqsiDPKk.png`
- **Site URL:** `https://ocean.security/`
- **Brand color:** `#99eeff`
- **Brand typeface:** Rethink Sans

## Quick Reference

```
Background:     #ffffff
Surface:        #eceff4
Text:           #002231 / #bababa
Accent:         #99eeff
Border:         #1e1f21
Font:           Rethink Sans
Spacing:        4px grid
Radius:         40px
Components:     6 detected
```

## When to Trigger

Activate this skill when:
- Creating new components, pages, or visual elements for ocean
- Writing CSS, Tailwind classes, styled-components, or inline styles
- Building page layouts, templates, or responsive designs
- Reviewing UI code for design consistency
- The user mentions "ocean" design, style, UI, or theme
- Generating mockups, wireframes, or visual prototypes

---

# Full Reference Files

> Every output file is embedded below. Claude has full design system context from /skills alone.

## Design System Tokens (DESIGN.md)

# ocean DESIGN.md

> Auto-generated design system — reverse-engineered via static analysis by skillui.
> Frameworks: None detected
> Colors: 20 · Fonts: 3 · Components: 6
> Icon library: not detected · State: not detected
> Primary theme: light · Dark mode toggle: no · Motion: subtle

## Visual Reference

**Match this design exactly** — study colors, fonts, spacing, and component shapes before writing any UI code.

![ocean Homepage](../screenshots/homepage.png)

---

## 1. Visual Theme & Atmosphere

This is a **light-themed** interface with a cool, approachable feel. The light background emphasizes content clarity. Typography pairs **DM Sans** for display/headings with **Rethink Sans** for body text, creating clear visual hierarchy through type contrast. Spacing follows a **4px base grid** (compact density), with scale: 2, 4, 6, 8, 10, 12, 14, 16px. The accent color **#99eeff** anchors interactive elements (buttons, links, focus rings). Motion is subtle — smooth transitions (150-300ms) ease state changes without drawing attention.

---

## 2. Color Palette & Roles

| Token | Hex | Role | Use |
|---|---|---|---|
| framer-link-hover-text-color | `#ffffff` | background | Page background, darkest surface |
| surface | `#eceff4` | surface | Card and panel backgrounds |
| framer-input-background | `#002231` | text-primary | Headings and body text |
| text-muted | `#bababa` | text-muted | Captions, placeholders, secondary info |
| border | `#1e1f21` | border | Dividers, card borders, outlines |
| accent | `#99eeff` | accent | CTAs, links, focus rings, active states |
| danger | `#eb8f49` | danger | Error states, destructive actions |
| warning | `#ffc375` | warning | Warning states, caution indicators |
| framer-link-text-color | `#0099ff` | info | Informational highlights |
| framer-text-color | `#000000` | unknown | Palette color |
| border-color | `#c1d3d8` | unknown | Palette color |
| unknown | `#d2dbe5` | unknown | Palette color |
| unknown | `#00141a` | unknown | Palette color |
| unknown | `#00313c` | unknown | Palette color |
| unknown | `#a3a3a3` | unknown | Palette color |
| unknown | `#12111c` | unknown | Palette color |
| framer-input-icon-color | `#999999` | unknown | Palette color |
| unknown | `#00394a` | unknown | Palette color |
| unknown | `#315159` | unknown | Palette color |
| unknown | `#73faff` | unknown | Palette color |

### CSS Variable Tokens

```css
--border-bottom-width: 1px;
--border-left-width: 1px;
--border-right-width: 1px;
--border-style: solid;
--border-top-width: 1px;
--framer-text-background-color: initial;
--framer-text-background-radius: initial;
--framer-text-background-corner-shape: initial;
--framer-text-background-padding: initial;
--border-bottom-width: .5px;
--border-left-width: .5px;
--border-right-width: .5px;
--border-style: solid;
--border-top-width: .5px;
--framer-input-background: #00243005;
--framer-input-border-bottom-width: 1px;
--framer-input-border-color: #0024308c;
--framer-input-border-left-width: 1px;
--framer-input-border-radius-bottom-left: 10px;
--framer-input-border-radius-bottom-right: 10px;
```


---

## 3. Typography Rules

**Font Stack:**
- **Rethink Sans** — Heading 1, Heading 2, Heading 3
- **DM Sans** — Body, Caption
- **Fragment Mono** — Code

**Font Sources:**

```css
@font-face {
  font-family: "DM Sans";
  src: url("fonts/DMSans-Bold.ttf") format("truetype");
  font-weight: 700;
}
@font-face {
  font-family: "DM Sans";
  src: url("fonts/DMSans-Regular.ttf") format("truetype");
  font-weight: 400;
}
@font-face {
  font-family: "Rethink Sans";
  src: url("fonts/RethinkSans-Bold.ttf") format("truetype");
  font-weight: 700;
}
@font-face {
  font-family: "Rethink Sans";
  src: url("fonts/RethinkSans-Regular.ttf") format("truetype");
  font-weight: 400;
}
@font-face {
  font-family: "Roboto";
  src: url("fonts/Roboto-Bold.ttf") format("truetype");
  font-weight: 700;
}
@font-face {
  font-family: "Roboto";
  src: url("fonts/Roboto-Regular.ttf") format("truetype");
  font-weight: 400;
}
@font-face {
  font-family: "Fragment Mono";
  src: url("fonts/FragmentMono-Regular.ttf") format("truetype");
  font-weight: 400;
}
@font-face {
  font-family: "Gloock";
  src: url("fonts/Gloock-Regular.ttf") format("truetype");
  font-weight: 400;
}
@font-face {
  font-family: "Inter";
  src: url("fonts/Inter-Bold.ttf") format("truetype");
  font-weight: 700;
}
@font-face {
  font-family: "Inter";
  src: url("fonts/Inter-Regular.ttf") format("truetype");
  font-weight: 400;
}
@font-face {
  font-family: "Satoshi";
  src: url("fonts/Satoshi-700.woff2") format("woff2");
  font-weight: 700;
}
@font-face {
  font-family: "Satoshi";
  src: url("fonts/Satoshi-Regular.woff2") format("woff2");
  font-weight: 400;
}
@font-face {
  font-family: "Manrope";
  src: url("fonts/Manrope-Bold.ttf") format("truetype");
  font-weight: 700;
}
@font-face {
  font-family: "Manrope";
  src: url("fonts/Manrope-Regular.ttf") format("truetype");
  font-weight: 400;
}
```

| Role | Font | Size | Weight |
|---|---|---|---|
| Heading 1 | Rethink Sans | calc(var(--framer-blockquote-font-size,var(--framer-font-size,16px))*var(--framer-font-size-scale,1)) | 700 |
| Heading 2 | Rethink Sans | calc(var(--framer-link-hover-font-size,var(--framer-blockquote-font-size,var(--framer-font-size,16px)))*var(--framer-font-size-scale,1)) | 700 |
| Heading 3 | Rethink Sans | calc(var(--framer-link-current-font-size,var(--framer-link-font-size,var(--framer-font-size,16px)))*var(--framer-font-size-scale,1)) | 700 |
| Body | DM Sans | calc(var(--framer-link-hover-font-size,var(--framer-link-current-font-size,var(--framer-link-font-size,var(--framer-font-size,16px))))*var(--framer-font-size-scale,1)) | 400 |
| Caption | DM Sans | var(--framer-font-size,16px) | 400 |
| Code | Fragment Mono | 14px | 400 |

**Typographic Rules:**
- Limit to 3 font families max per screen
- Use **Rethink Sans** for body/UI text, **DM Sans** for display/headings
- Maintain consistent hierarchy: no more than 3-4 font sizes per screen
- Headings use bold (600-700), body uses regular (400)
- Line height: 1.5 for body text, 1.2 for headings
- Use color and opacity for secondary hierarchy, not additional font sizes


---

## 4. Component Stylings

### Layout (1)

**Footer** — `html`

### Data Input (2)

**Button** — `html`

**Input** — `html`
- State: :focus, :placeholder

### Media (3)

**Image** — `html`

**Icon** — `html`

**Map/Canvas** — `html`



---

## 5. Layout Principles

- **Base spacing unit:** 4px
- **Spacing scale:** 2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22, 24
- **Border radius:** 5px, 6px, 8px, 11px, 20px, 30px, 40px, 100%, 140px, 180px, 470px, 500px, inherit
- **Max content width:** 1199px

**Spacing as Meaning:**
| Spacing | Use |
|---|---|
| 4-8px | Tight: related items within a group |
| 12-16px | Medium: between groups |
| 24-32px | Wide: between sections |
| 48px+ | Vast: major section breaks |


---

## 6. Depth & Elevation

### Raised — cards, buttons, interactive elements

- `unset`
- `var(--framer-input-box-shadow)`
- `var(--framer-input-focused-box-shadow,var(--framer-input-box-shadow))`

### Overlay — full-screen overlays, top-level dialogs

- `inset .557334px .358286px 1.45764px -1.125px #ffffff38,inset 1.69015px 1.08653px 4.42039px -2.25px #fff3,inset 4.46786px 2.87219px 11.6851px -3.375px #ffffff29,inset 14px 9px 36.6153px -4.5px #ffffff05`
- `inset .906987px .151164px 2.02289px -.5625px #ffffff08,inset 2.14972px .358286px 4.79462px -1.125px #ffffff08,inset 3.92131px .653551px 8.74587px -1.6875px #ffffff08,inset 6.51917px 1.08653px 14.54px -2.25px #ffffff05,inset 10.5279px 1.75465px 23.4809px -2.8125px #ffffff05,inset 17.2332px 2.87219px 38.4359px -3.375px #ffffff05,inset 29.6743px 4.94572px 66.1841px -3.9375px #ffffff03,inset 54px 9px 120.439px -4.5px #fff0`
- `10px 11px 32px -20px #00000040`

### Z-Index Scale

`0, 1, 2, 3, 4, 5, 10`



---

## 7. Animation & Motion

This project uses **subtle motion**. Transitions smooth state changes without demanding attention.

### Motion Guidelines

- Duration: 150-300ms for micro-interactions, 300-500ms for page transitions
- Easing: `ease-out` for enters, `ease-in` for exits
- Always respect `prefers-reduced-motion`


---

## 8. Do's and Don'ts

### Do's

- Use `#99eeff` for interactive elements (buttons, links, focus rings)
- Use `#ffffff` as the primary page background
- Pair **Rethink Sans** (body) with **DM Sans** (display) — these are the only allowed fonts
- Follow the **4px** spacing grid for all margins, padding, and gaps
- Use the defined shadow tokens for elevation — see Section 6
- Use border-radius from the scale: 5px, 6px, 8px, 11px, 20px
- Reuse existing components from Section 4 before creating new ones

### Don'ts

- Don't introduce colors outside this palette — extend the design tokens first
- Don't introduce additional font families beyond Rethink Sans and DM Sans and Fragment Mono
- Don't use arbitrary spacing values — stick to multiples of 4px
- Don't create custom box-shadow values outside the system tokens
- Don't use arbitrary border-radius values — pick from the defined scale
- Don't duplicate component patterns — check Section 4 first
- Don't use backdrop-blur or blur effects

### Anti-Patterns (detected from codebase)

- No blur or backdrop-blur effects
- No zebra striping on tables/lists


---

## 9. Responsive Behavior

| Name | Value | Source |
|---|---|---|
| lg | 809px | css |
| lg | 809.98px | css |
| lg | 810px | css |
| xl | 1199px | css |
| xl | 1199.98px | css |
| xl | 1200px | css |
| 2xl | 1326px | css |
| 2xl | 1326.98px | css |
| 2xl | 1327px | css |

**Approach:** Use `@media (min-width: ...)` queries matching the breakpoints above.


---

## 10. Agent Prompt Guide

Use these as starting points when building new UI:

### Build a Card

```
Background: #eceff4
Border: 1px solid #1e1f21
Radius: 40px
Padding: 16px
Font: Rethink Sans
Use shadow tokens from Section 6.
```

### Build a Button

```
Primary: bg #99eeff, text white
Ghost: bg transparent, border #1e1f21
Padding: 8px 16px
Radius: 40px
Hover: opacity 0.9 or lighter shade
Focus: ring with #99eeff
```

### Build a Page Layout

```
Background: #ffffff
Max-width: 1199px, centered
Grid: 4px base
Responsive: mobile-first, breakpoints from Section 9
```

### Build a Stats Card

```
Surface: #eceff4
Label: #bababa (muted, 12px, uppercase)
Value: #002231 (primary, 24-32px, bold)
Status: use success/warning/danger from Section 2
```

### Build a Form

```
Input bg: #ffffff
Input border: 1px solid #1e1f21
Focus: border-color #99eeff
Label: #bababa 12px
Spacing: 16px between fields
Radius: 40px
```

### General Component

```
1. Read DESIGN.md Sections 2-6 for tokens
2. Colors: only from palette
3. Font: Rethink Sans, type scale from Section 3
4. Spacing: 4px grid
5. Components: match patterns from Section 4
6. Elevation: shadow tokens
```

## Bundled Fonts (fonts/)

The following font files are bundled in the `fonts/` directory:

- `fonts/DMSans-Black.ttf`
- `fonts/DMSans-Bold.ttf`
- `fonts/DMSans-ExtraBold.ttf`
- `fonts/DMSans-ExtraLight.ttf`
- `fonts/DMSans-Light.ttf`
- `fonts/DMSans-Medium.ttf`
- `fonts/DMSans-Regular.ttf`
- `fonts/DMSans-SemiBold.ttf`
- `fonts/DMSans-Thin.ttf`
- `fonts/FragmentMono-Regular.ttf`
- `fonts/Gloock-Regular.ttf`
- `fonts/Inter-Black.ttf`
- `fonts/Inter-Bold.ttf`
- `fonts/Inter-ExtraBold.ttf`
- `fonts/Inter-ExtraLight.ttf`
- `fonts/Inter-Light.ttf`
- `fonts/Inter-Medium.ttf`
- `fonts/Inter-Regular.ttf`
- `fonts/Inter-SemiBold.ttf`
- `fonts/Inter-Thin.ttf`
- `fonts/Manrope-Bold.ttf`
- `fonts/Manrope-ExtraBold.ttf`
- `fonts/Manrope-ExtraLight.ttf`
- `fonts/Manrope-Light.ttf`
- `fonts/Manrope-Medium.ttf`
- `fonts/Manrope-Regular.ttf`
- `fonts/Manrope-SemiBold.ttf`
- `fonts/RethinkSans-Bold.ttf`
- `fonts/RethinkSans-ExtraBold.ttf`
- `fonts/RethinkSans-Medium.ttf`
- `fonts/RethinkSans-Regular.ttf`
- `fonts/RethinkSans-SemiBold.ttf`
- `fonts/Roboto-Black.ttf`
- `fonts/Roboto-Bold.ttf`
- `fonts/Roboto-ExtraBold.ttf`
- `fonts/Roboto-ExtraLight.ttf`
- `fonts/Roboto-Light.ttf`
- `fonts/Roboto-Medium.ttf`
- `fonts/Roboto-Regular.ttf`
- `fonts/Roboto-SemiBold.ttf`
- `fonts/Roboto-Thin.ttf`
- `fonts/Satoshi-500.woff2`
- `fonts/Satoshi-700.woff2`
- `fonts/Satoshi-900.woff2`
- `fonts/Satoshi-Regular.woff2`

Use these local font files in `@font-face` declarations instead of fetching from Google Fonts.

## Homepage Screenshots (screenshots/)

![homepage.png](screenshots/homepage.png)

