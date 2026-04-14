# RAG Studio Visual Redesign — CSS & HTML Changes

## Color Tokens (CSS Custom Properties)
Add to `:root`:
```css
--bg:        #F5F2EC;
--surface:   #EAE5DA;
--ink:       #1A1A18;
--ink-muted: #6B6660;
--border:    rgba(26,26,24,0.12);
```

## Font Imports (Add at top of styles.css)
```css
@import url('https://fonts.googleapis.com/css2?family=EB+Garamond:ital,wght@0,400;0,500;1,400&family=DM+Mono:wght@400;500&display=swap');
```

## Typography Tokens (Add to :root)
```css
--font-editorial: 'EB Garamond', Georgia, serif;
--font-mono:      'DM Mono', 'Courier New', monospace;
```

---

## Complete New styles.css

Replace the entire `static/css/styles.css` with the file content provided below.

---

## HTML Changes Required

### 1. Update Navbar "Backend OK" Status Badge (studio.html line ~38)

**BEFORE:**
```html
<span id="backend-status" class="badge">Checking...</span>
```

**AFTER:**
```html
<span id="backend-status" class="backend-status-pill">Checking…</span>
```

**Note**: Change class from `badge` to `backend-status-pill` (CSS-only change, no JS affected)

---

### 2. Update "Reset Session" Button (studio.html line ~39)

**BEFORE:**
```html
<button id="reset-btn" class="btn nav-cta" type="button">Reset Session</button>
```

**AFTER:**
```html
<button id="reset-btn" class="reset-session-btn" type="button">Reset Session</button>
```

**Note**: Remove `btn nav-cta` classes, replace with `reset-session-btn` (CSS-only, no JS affected)

---

### 3. Panel Numbers Format (studio.html multiple locations)

Each panel has a `<span class="studio-panel-num">01</span>` element. These are correct but the CSS changes how they display. No HTML changes needed — the CSS will show them as "01 —" text format.

---

### 4. Remove Colored Badges (studio.html)

Currently there are inline badges like:
```html
<span class="chunk-badge">104 chunks</span>
```

Keep this HTML as-is. CSS will change its styling to the light theme. No HTML removal needed.

---

### 5. Icon SVGs (studio.html)

Keep all SVG icons (upload icon, document icon, etc.) as-is. Update stroke/fill colors via CSS.

---

## Implementation Steps

1. **Replace entire `static/css/styles.css`** with the new CSS (see next section)
2. **Update navbar status badge class** (line ~38): `badge` → `backend-status-pill`
3. **Update reset button classes** (line ~39): `btn nav-cta` → `reset-session-btn`
4. **No other HTML changes required**

---

## CSS Architecture

### Sections in New File
1. **CSS Variables + Global Resets** — New color tokens, typography, removed gradients
2. **Site Shell & Layout** — Beige background, removed gradients
3. **Navbar** — Light theme with monospace branding
4. **Badges & Status Pills** — Minimal borders, no color coding
5. **Studio Layout** — 3-column grid maintained
6. **Studio Panels** — Light surfaces with minimal borders
7. **Form Fields** — Beige backgrounds, minimal borders
8. **Drop Zone** — Dashed border, light background
9. **Buttons** — Dark ink on light, inverted on hover
10. **Pipeline Tracker** — Monospace labels, simple dots, no colors
11. **Query Panel** — Light textarea, minimal border
12. **Response Panel** — Light background, serif text, italic empty state
13. **Documents Panel** — Light cards, minimal borders, no gradients
14. **Evaluation Panel** — Light background, monospace labels, no colored bars
15. **Loading Overlay** — Light beige with minimal contrast
16. **Responsive** — Maintained as-is

---

## Key Removals
- ❌ All dark backgrounds (#1a1a26, #1f1f2e, etc.)
- ❌ All orange/red accents (var(--accent))
- ❌ All colored gradients (linear-gradient, radial-gradient)
- ❌ Neon glows (box-shadow with accent colors)
- ❌ Colored pulses and animations
- ❌ Backdrop blur effects
- ❌ Color-coded status indicators (green=ok, red=error, orange=warning)

## Key Additions
- ✅ EB Garamond serif font for editorial feel
- ✅ DM Mono for monospace labels and counters
- ✅ Beige color palette (#F5F2EC → #EAE5DA → backgrounds)
- ✅ Simple 0.5px borders throughout
- ✅ Monospace panel numbers with "—" separator (CSS content)
- ✅ Minimal visual hierarchy via typography size/weight only
- ✅ Italic placeholder text for empty states
- ✅ Hover states: background inversion (ink on light → light on ink)

