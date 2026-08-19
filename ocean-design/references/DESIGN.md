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
