# AbaQuiz Web Admin - UI Design Plan

## Overview

This document provides implementation-ready design specifications for migrating the AbaQuiz web admin interface from Pico CSS to Tailwind CSS while maintaining HTMX + Alpine.js integration.

**Design Philosophy**: Dark minimal, Notion-inspired aesthetic with clean blocks, subtle borders, and excellent typography. Optimized for data density and administrative workflows.

---

## 1. Color Palette

### 1.1 Semantic Color Tokens (CSS Custom Properties)

```css
:root {
  /* ============================================
     LIGHT THEME (Default)
     ============================================ */

  /* Background Layers */
  --color-bg-base: #ffffff;
  --color-bg-subtle: #f8fafa;
  --color-bg-muted: #f1f5f5;
  --color-bg-emphasis: #e8eeee;

  /* Surface (Cards, Modals, Dropdowns) */
  --color-surface-primary: #ffffff;
  --color-surface-secondary: #f8fafa;
  --color-surface-elevated: #ffffff;

  /* Border */
  --color-border-default: #e2e8e8;
  --color-border-muted: #eef2f2;
  --color-border-emphasis: #cbd5d5;

  /* Text */
  --color-text-primary: #1a2626;
  --color-text-secondary: #4a5858;
  --color-text-muted: #6b7a7a;
  --color-text-disabled: #9ca8a8;
  --color-text-inverse: #ffffff;

  /* Primary (Teal/Cyan) */
  --color-primary-50: #ecfeff;
  --color-primary-100: #cffafe;
  --color-primary-200: #a5f3fc;
  --color-primary-300: #67e8f9;
  --color-primary-400: #22d3ee;
  --color-primary-500: #06b6d4;
  --color-primary-600: #0891b2;
  --color-primary-700: #0e7490;
  --color-primary-800: #155e75;
  --color-primary-900: #164e63;

  /* Primary Semantic */
  --color-primary: #0891b2;
  --color-primary-hover: #0e7490;
  --color-primary-active: #155e75;
  --color-primary-subtle: #ecfeff;
  --color-primary-muted: #cffafe;

  /* Success (Green) */
  --color-success: #059669;
  --color-success-subtle: #ecfdf5;
  --color-success-border: #a7f3d0;

  /* Warning (Amber) */
  --color-warning: #d97706;
  --color-warning-subtle: #fffbeb;
  --color-warning-border: #fde68a;

  /* Error (Red) */
  --color-error: #dc2626;
  --color-error-subtle: #fef2f2;
  --color-error-border: #fecaca;

  /* Info (Blue) */
  --color-info: #2563eb;
  --color-info-subtle: #eff6ff;
  --color-info-border: #bfdbfe;

  /* Neutral (For badges) */
  --color-neutral: #6b7a7a;
  --color-neutral-subtle: #f1f5f5;
  --color-neutral-border: #e2e8e8;

  /* Interactive States */
  --color-focus-ring: rgba(8, 145, 178, 0.4);
  --color-hover-overlay: rgba(0, 0, 0, 0.04);
  --color-active-overlay: rgba(0, 0, 0, 0.08);

  /* Shadows */
  --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.05);
  --shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.07), 0 2px 4px -1px rgba(0, 0, 0, 0.04);
  --shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.08), 0 4px 6px -2px rgba(0, 0, 0, 0.04);
  --shadow-xl: 0 20px 25px -5px rgba(0, 0, 0, 0.08), 0 10px 10px -5px rgba(0, 0, 0, 0.03);

  /* Sidebar */
  --sidebar-bg: #f8fafa;
  --sidebar-border: #e2e8e8;
  --sidebar-item-hover: #e8eeee;
  --sidebar-item-active: #e8eeee;
  --sidebar-item-active-border: #0891b2;
}

[data-theme="dark"] {
  /* ============================================
     DARK THEME
     ============================================ */

  /* Background Layers */
  --color-bg-base: #0f1414;
  --color-bg-subtle: #161c1c;
  --color-bg-muted: #1e2626;
  --color-bg-emphasis: #283030;

  /* Surface (Cards, Modals, Dropdowns) */
  --color-surface-primary: #161c1c;
  --color-surface-secondary: #1e2626;
  --color-surface-elevated: #1e2626;

  /* Border */
  --color-border-default: #2d3838;
  --color-border-muted: #242e2e;
  --color-border-emphasis: #3d4a4a;

  /* Text */
  --color-text-primary: #f0f4f4;
  --color-text-secondary: #a8b8b8;
  --color-text-muted: #7a8a8a;
  --color-text-disabled: #4a5858;
  --color-text-inverse: #0f1414;

  /* Primary (Teal/Cyan - adjusted for dark) */
  --color-primary: #22d3ee;
  --color-primary-hover: #67e8f9;
  --color-primary-active: #a5f3fc;
  --color-primary-subtle: #164e63;
  --color-primary-muted: #155e75;

  /* Success (Green) */
  --color-success: #34d399;
  --color-success-subtle: #064e3b;
  --color-success-border: #065f46;

  /* Warning (Amber) */
  --color-warning: #fbbf24;
  --color-warning-subtle: #78350f;
  --color-warning-border: #92400e;

  /* Error (Red) */
  --color-error: #f87171;
  --color-error-subtle: #7f1d1d;
  --color-error-border: #991b1b;

  /* Info (Blue) */
  --color-info: #60a5fa;
  --color-info-subtle: #1e3a5f;
  --color-info-border: #1e40af;

  /* Neutral (For badges) */
  --color-neutral: #a8b8b8;
  --color-neutral-subtle: #1e2626;
  --color-neutral-border: #2d3838;

  /* Interactive States */
  --color-focus-ring: rgba(34, 211, 238, 0.4);
  --color-hover-overlay: rgba(255, 255, 255, 0.04);
  --color-active-overlay: rgba(255, 255, 255, 0.08);

  /* Shadows (more subtle in dark mode) */
  --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.3);
  --shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.4), 0 2px 4px -1px rgba(0, 0, 0, 0.3);
  --shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.4), 0 4px 6px -2px rgba(0, 0, 0, 0.3);
  --shadow-xl: 0 20px 25px -5px rgba(0, 0, 0, 0.5), 0 10px 10px -5px rgba(0, 0, 0, 0.3);

  /* Sidebar */
  --sidebar-bg: #161c1c;
  --sidebar-border: #2d3838;
  --sidebar-item-hover: #1e2626;
  --sidebar-item-active: #1e2626;
  --sidebar-item-active-border: #22d3ee;
}
```

### 1.2 Tailwind Config Extension

```javascript
// tailwind.config.js
module.exports = {
  darkMode: ['class', '[data-theme="dark"]'],
  theme: {
    extend: {
      colors: {
        // Primary Teal/Cyan
        primary: {
          50: '#ecfeff',
          100: '#cffafe',
          200: '#a5f3fc',
          300: '#67e8f9',
          400: '#22d3ee',
          500: '#06b6d4',
          600: '#0891b2',
          700: '#0e7490',
          800: '#155e75',
          900: '#164e63',
        },
        // Custom grays with teal undertone
        surface: {
          light: {
            base: '#ffffff',
            subtle: '#f8fafa',
            muted: '#f1f5f5',
            emphasis: '#e8eeee',
          },
          dark: {
            base: '#0f1414',
            subtle: '#161c1c',
            muted: '#1e2626',
            emphasis: '#283030',
          }
        }
      },
    },
  },
}
```

---

## 2. Typography

### 2.1 Font Stack

```css
:root {
  /* Primary font - System UI for performance */
  --font-sans: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont,
               "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;

  /* Monospace for code/data */
  --font-mono: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas,
               "Liberation Mono", monospace;

  /* Optional: Inter for polished feel (requires font import) */
  /* --font-sans: "Inter", ui-sans-serif, system-ui, sans-serif; */
}
```

### 2.2 Type Scale

| Token | Size | Line Height | Weight | Usage |
|-------|------|-------------|--------|-------|
| `text-xs` | 12px (0.75rem) | 16px (1.33) | 400/500 | Badges, timestamps, helper text |
| `text-sm` | 14px (0.875rem) | 20px (1.43) | 400/500 | Body text, table cells, inputs |
| `text-base` | 16px (1rem) | 24px (1.5) | 400/500 | Primary body, buttons |
| `text-lg` | 18px (1.125rem) | 28px (1.56) | 500/600 | Subheadings, card titles |
| `text-xl` | 20px (1.25rem) | 28px (1.4) | 600 | Section headers |
| `text-2xl` | 24px (1.5rem) | 32px (1.33) | 600 | Page titles |
| `text-3xl` | 30px (1.875rem) | 36px (1.2) | 700 | Dashboard metrics |

### 2.3 Font Weights

| Weight | Value | Usage |
|--------|-------|-------|
| Normal | 400 | Body text, descriptions |
| Medium | 500 | Labels, navigation items, badges |
| Semibold | 600 | Headings, card titles, emphasis |
| Bold | 700 | Page titles, large metrics |

### 2.4 Letter Spacing

| Token | Value | Usage |
|-------|-------|-------|
| `tracking-tight` | -0.025em | Headings (text-xl and up) |
| `tracking-normal` | 0 | Body text |
| `tracking-wide` | 0.025em | Uppercase labels, badges |

---

## 3. Spacing System

### 3.1 Base Scale (4px increments)

| Token | Value | Common Usage |
|-------|-------|--------------|
| `0` | 0px | Reset |
| `0.5` | 2px | Micro gaps |
| `1` | 4px | Icon gaps, tight padding |
| `1.5` | 6px | Compact elements |
| `2` | 8px | Small padding, icon margins |
| `2.5` | 10px | Badge padding |
| `3` | 12px | Input padding, card gaps |
| `4` | 16px | Standard padding, section gaps |
| `5` | 20px | Medium spacing |
| `6` | 24px | Card padding, large gaps |
| `8` | 32px | Section spacing |
| `10` | 40px | Large section spacing |
| `12` | 48px | Page margins |
| `16` | 64px | Layout spacing |
| `20` | 80px | Major sections |

### 3.2 Layout-Specific Spacing

```css
:root {
  /* Sidebar */
  --sidebar-width-expanded: 240px;
  --sidebar-width-collapsed: 64px;
  --sidebar-padding: 12px;
  --sidebar-item-padding: 8px 12px;
  --sidebar-item-gap: 4px;

  /* Content Area */
  --content-padding-x: 24px;
  --content-padding-y: 24px;
  --content-max-width: 1400px;

  /* Cards */
  --card-padding: 20px;
  --card-padding-sm: 16px;
  --card-gap: 16px;
  --card-border-radius: 8px;

  /* Tables */
  --table-cell-padding-x: 12px;
  --table-cell-padding-y: 10px;
  --table-header-padding-y: 12px;

  /* Form Elements */
  --input-padding-x: 12px;
  --input-padding-y: 10px;
  --input-border-radius: 6px;

  /* Buttons */
  --btn-padding-x: 16px;
  --btn-padding-y: 10px;
  --btn-padding-x-sm: 12px;
  --btn-padding-y-sm: 6px;
  --btn-border-radius: 6px;
}
```

---

## 4. Component Specifications

### 4.1 Sidebar Navigation

#### Structure
```
+------------------+
| Logo/Brand       |
| [Collapse btn]   |
+------------------+
| Nav Items        |
| - Dashboard      |
| - Questions      |
| - Tables         |
| - Settings       |
+------------------+
| Footer           |
| [Theme Toggle]   |
+------------------+
```

#### States

**Expanded (Desktop Default)**
- Width: 240px
- Logo: Full text "AbaQuiz Admin"
- Nav items: Icon (20px) + Label + Gap (12px)
- Item padding: 8px 12px
- Item border-radius: 6px

**Collapsed (Mobile/Toggle)**
- Width: 64px
- Logo: Icon only or "AQ"
- Nav items: Icon only (centered)
- Tooltip on hover showing label

#### Styling

```css
/* Sidebar Container */
.sidebar {
  width: var(--sidebar-width-expanded);
  background: var(--sidebar-bg);
  border-right: 1px solid var(--sidebar-border);
  display: flex;
  flex-direction: column;
  height: 100vh;
  position: fixed;
  left: 0;
  top: 0;
  transition: width 200ms ease;
  z-index: 40;
}

.sidebar.collapsed {
  width: var(--sidebar-width-collapsed);
}

/* Nav Item */
.nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 12px;
  border-radius: 6px;
  color: var(--color-text-secondary);
  font-size: 14px;
  font-weight: 500;
  text-decoration: none;
  transition: all 150ms ease;
  margin: 2px 8px;
}

.nav-item:hover {
  background: var(--sidebar-item-hover);
  color: var(--color-text-primary);
}

.nav-item.active {
  background: var(--sidebar-item-active);
  color: var(--color-primary);
  border-left: 2px solid var(--sidebar-item-active-border);
  margin-left: 6px;
  padding-left: 10px;
}

/* Nav Icon */
.nav-item svg {
  width: 20px;
  height: 20px;
  flex-shrink: 0;
}

/* Collapsed state */
.sidebar.collapsed .nav-item {
  justify-content: center;
  padding: 12px;
}

.sidebar.collapsed .nav-item span {
  display: none;
}
```

#### Tailwind Classes

```html
<!-- Expanded Sidebar -->
<aside class="fixed left-0 top-0 h-screen w-60 bg-surface-light-subtle dark:bg-surface-dark-subtle
              border-r border-border-default flex flex-col transition-all duration-200 z-40"
       :class="{ 'w-16': collapsed }">

  <!-- Header -->
  <div class="h-16 flex items-center px-4 border-b border-border-default">
    <span class="font-semibold text-lg text-text-primary" x-show="!collapsed">AbaQuiz Admin</span>
    <span class="font-bold text-primary-600 dark:text-primary-400" x-show="collapsed">AQ</span>
  </div>

  <!-- Navigation -->
  <nav class="flex-1 py-4 overflow-y-auto">
    <a href="/" class="flex items-center gap-3 mx-2 px-3 py-2 rounded-md text-sm font-medium
                       text-text-secondary hover:bg-bg-emphasis hover:text-text-primary
                       [&.active]:bg-bg-emphasis [&.active]:text-primary-600
                       [&.active]:border-l-2 [&.active]:border-primary-600">
      <svg class="w-5 h-5 flex-shrink-0"><!-- Icon --></svg>
      <span x-show="!collapsed">Dashboard</span>
    </a>
  </nav>

  <!-- Footer -->
  <div class="p-4 border-t border-border-default">
    <!-- Theme toggle here -->
  </div>
</aside>
```

---

### 4.2 Dashboard Cards (Stats Cards)

#### Layout
- Grid: 4 columns on desktop, 2 on tablet, 1 on mobile
- Full-width row below for recent activity

#### Card Structure
```
+------------------------+
| Icon    |    Metric    |
|         |    Label     |
|         |    Change    |
+------------------------+
```

#### Styling

```css
.stat-card {
  background: var(--color-surface-primary);
  border: 1px solid var(--color-border-default);
  border-radius: 8px;
  padding: 20px;
  display: flex;
  align-items: flex-start;
  gap: 16px;
}

.stat-card-icon {
  width: 40px;
  height: 40px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--color-primary-subtle);
  color: var(--color-primary);
}

.stat-card-content {
  flex: 1;
}

.stat-card-value {
  font-size: 28px;
  font-weight: 700;
  line-height: 1.2;
  color: var(--color-text-primary);
  letter-spacing: -0.025em;
}

.stat-card-label {
  font-size: 14px;
  color: var(--color-text-muted);
  margin-top: 2px;
}

.stat-card-change {
  font-size: 12px;
  margin-top: 8px;
}

.stat-card-change.positive {
  color: var(--color-success);
}

.stat-card-change.negative {
  color: var(--color-error);
}
```

#### Tailwind Implementation

```html
<div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
  <article class="bg-surface-primary border border-border-default rounded-lg p-5 flex items-start gap-4">
    <div class="w-10 h-10 rounded-lg bg-primary-50 dark:bg-primary-900/30
                flex items-center justify-center text-primary-600 dark:text-primary-400">
      <svg class="w-5 h-5"><!-- Icon --></svg>
    </div>
    <div>
      <p class="text-3xl font-bold tracking-tight text-text-primary">247</p>
      <p class="text-sm text-text-muted mt-0.5">Total Questions</p>
      <p class="text-xs text-success mt-2">+12 this week</p>
    </div>
  </article>
</div>
```

---

### 4.3 Data Tables

#### Structure
- Sticky header on scroll
- Sortable columns with indicators
- Row hover state
- Compact density by default

#### Styling

```css
.data-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
}

.data-table thead {
  position: sticky;
  top: 0;
  background: var(--color-bg-subtle);
  z-index: 10;
}

.data-table th {
  padding: 12px;
  text-align: left;
  font-weight: 500;
  color: var(--color-text-secondary);
  border-bottom: 1px solid var(--color-border-default);
  white-space: nowrap;
}

.data-table th a {
  color: inherit;
  text-decoration: none;
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.data-table th a:hover {
  color: var(--color-text-primary);
}

.data-table td {
  padding: 10px 12px;
  border-bottom: 1px solid var(--color-border-muted);
  color: var(--color-text-primary);
  max-width: 300px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.data-table tbody tr:hover {
  background: var(--color-hover-overlay);
}

.data-table tbody tr:last-child td {
  border-bottom: none;
}

/* Sort indicators */
.sort-asc::after {
  content: "\\2191"; /* Up arrow */
  margin-left: 4px;
  opacity: 0.6;
}

.sort-desc::after {
  content: "\\2193"; /* Down arrow */
  margin-left: 4px;
  opacity: 0.6;
}
```

#### Tailwind Implementation

```html
<div class="overflow-x-auto border border-border-default rounded-lg">
  <table class="w-full text-sm">
    <thead class="sticky top-0 bg-bg-subtle">
      <tr>
        <th class="px-3 py-3 text-left font-medium text-text-secondary border-b border-border-default">
          <a href="#" class="inline-flex items-center gap-1 hover:text-text-primary">
            Name
            <svg class="w-4 h-4 opacity-60"><!-- Sort icon --></svg>
          </a>
        </th>
      </tr>
    </thead>
    <tbody class="divide-y divide-border-muted">
      <tr class="hover:bg-hover-overlay transition-colors">
        <td class="px-3 py-2.5 text-text-primary truncate max-w-xs">Value</td>
      </tr>
    </tbody>
  </table>
</div>
```

---

### 4.4 Question Cards (Full-Width)

#### Layout Specification
- **Width**: 100% of content area (one card per row)
- **All info visible**: No truncation of question text or options
- **Expandable sections**: Explanation only

#### Structure
```
+------------------------------------------------------------------+
| #ID | [Content Area Badge] | Difficulty Stars | Date       Right |
+------------------------------------------------------------------+
| Question Text (full, may wrap to multiple lines)                 |
|                                                                  |
| +------------+ +------------+ +------------+ +------------+      |
| | A) Option  | | B) Option  | | C) Option  | | D) Option  |      |
| +------------+ +------------+ +------------+ +------------+      |
|                                                                  |
| [Show Explanation] [View Details]                                |
+------------------------------------------------------------------+
| Explanation (collapsible, shown when toggled)                    |
+------------------------------------------------------------------+
```

#### Detailed Styling

```css
.question-card {
  background: var(--color-surface-primary);
  border: 1px solid var(--color-border-default);
  border-radius: 8px;
  margin-bottom: 16px;
  transition: box-shadow 200ms ease, border-color 200ms ease;
}

.question-card:hover {
  border-color: var(--color-border-emphasis);
  box-shadow: var(--shadow-sm);
}

/* Header */
.question-card-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px 20px;
  border-bottom: 1px solid var(--color-border-muted);
  flex-wrap: wrap;
}

.question-id {
  font-size: 13px;
  font-weight: 600;
  color: var(--color-text-muted);
  font-family: var(--font-mono);
}

.difficulty-stars {
  color: var(--color-warning);
  font-size: 14px;
  letter-spacing: 2px;
}

.question-date {
  margin-left: auto;
  font-size: 13px;
  color: var(--color-text-muted);
}

/* Body */
.question-card-body {
  padding: 20px;
}

.question-text {
  font-size: 15px;
  line-height: 1.6;
  color: var(--color-text-primary);
  margin-bottom: 16px;
}

/* Options Grid - 2x2 on desktop, 1 column on mobile */
.options-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px;
}

@media (max-width: 640px) {
  .options-grid {
    grid-template-columns: 1fr;
  }
}

.option {
  display: flex;
  gap: 10px;
  padding: 12px 14px;
  background: var(--color-bg-subtle);
  border: 1px solid var(--color-border-muted);
  border-radius: 6px;
  font-size: 14px;
  line-height: 1.5;
}

.option.correct {
  background: var(--color-success-subtle);
  border-color: var(--color-success-border);
  border-left-width: 3px;
  border-left-color: var(--color-success);
}

.option-key {
  font-weight: 600;
  color: var(--color-text-muted);
  flex-shrink: 0;
  width: 24px;
}

.option-text {
  color: var(--color-text-primary);
}

/* Footer */
.question-card-footer {
  display: flex;
  gap: 10px;
  padding: 16px 20px;
  border-top: 1px solid var(--color-border-muted);
}

/* Explanation */
.question-explanation {
  padding: 0 20px 20px;
  margin-top: -4px;
}

.question-explanation blockquote {
  margin: 0;
  padding: 16px;
  background: var(--color-bg-subtle);
  border-left: 3px solid var(--color-primary);
  border-radius: 0 6px 6px 0;
  font-size: 14px;
  line-height: 1.6;
  color: var(--color-text-secondary);
}
```

#### Tailwind Implementation

```html
<article class="bg-surface-primary border border-border-default rounded-lg mb-4
                hover:border-border-emphasis hover:shadow-sm transition-all">
  <!-- Header -->
  <header class="flex items-center gap-3 px-5 py-4 border-b border-border-muted flex-wrap">
    <span class="text-xs font-semibold text-text-muted font-mono">#{{ q.id }}</span>
    <span class="badge-neutral">{{ q.content_area }}</span>
    <span class="text-sm text-warning tracking-widest">{{ stars }}</span>
    <span class="ml-auto text-xs text-text-muted">{{ q.created_at }}</span>
  </header>

  <!-- Body -->
  <div class="p-5">
    <p class="text-[15px] leading-relaxed text-text-primary mb-4">
      {{ q.content }}
    </p>

    <div class="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
      <div class="flex gap-2.5 p-3 bg-bg-subtle border border-border-muted rounded-md text-sm
                  [&.correct]:bg-success-subtle [&.correct]:border-success-border
                  [&.correct]:border-l-[3px] [&.correct]:border-l-success">
        <span class="font-semibold text-text-muted w-6 flex-shrink-0">A)</span>
        <span class="text-text-primary">{{ option_a }}</span>
      </div>
      <!-- Repeat for B, C, D -->
    </div>
  </div>

  <!-- Footer -->
  <footer class="flex gap-2.5 px-5 py-4 border-t border-border-muted">
    <button class="btn-secondary-sm" @click="showExplanation = !showExplanation">
      <span x-text="showExplanation ? 'Hide Explanation' : 'Show Explanation'"></span>
    </button>
    <a href="/tables/questions/{{ q.id }}" class="btn-ghost-sm">View Details</a>
  </footer>

  <!-- Explanation (Collapsible) -->
  <div class="px-5 pb-5 -mt-1" x-show="showExplanation" x-collapse>
    <blockquote class="m-0 p-4 bg-bg-subtle border-l-[3px] border-l-primary
                       rounded-r-md text-sm leading-relaxed text-text-secondary">
      <strong class="text-text-primary">Correct: {{ q.correct_answer }}</strong><br>
      {{ q.explanation }}
    </blockquote>
  </div>
</article>
```

---

### 4.5 Content Area Badges (Muted/Neutral Style)

Per requirements: **Subtle/muted gray badges with text only (not colorful)**

```css
/* Single neutral badge style for all content areas */
.badge-neutral {
  display: inline-flex;
  align-items: center;
  padding: 4px 10px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 500;
  letter-spacing: 0.01em;
  white-space: nowrap;

  /* Light mode */
  background: var(--color-neutral-subtle);
  color: var(--color-text-secondary);
  border: 1px solid var(--color-neutral-border);
}

[data-theme="dark"] .badge-neutral {
  background: var(--color-neutral-subtle);
  color: var(--color-text-secondary);
  border-color: var(--color-neutral-border);
}
```

#### Tailwind Implementation

```html
<!-- Single style for all content areas -->
<span class="inline-flex items-center px-2.5 py-1 rounded text-xs font-medium
             bg-neutral-subtle text-text-secondary border border-neutral-border">
  Ethics
</span>
```

---

### 4.6 Buttons

#### Variants

| Variant | Usage |
|---------|-------|
| Primary | Main actions (Save, Submit, Create) |
| Secondary | Secondary actions (Cancel, Reset) |
| Ghost | Tertiary actions, links styled as buttons |
| Danger | Destructive actions (Delete, Remove) |

#### Sizes

| Size | Padding | Font Size | Height |
|------|---------|-----------|--------|
| Small (sm) | 6px 12px | 13px | 32px |
| Default | 10px 16px | 14px | 40px |
| Large (lg) | 12px 20px | 15px | 48px |

#### Styling

```css
/* Base button */
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 10px 16px;
  font-size: 14px;
  font-weight: 500;
  line-height: 1;
  border-radius: 6px;
  border: 1px solid transparent;
  cursor: pointer;
  transition: all 150ms ease;
  white-space: nowrap;
}

.btn:focus-visible {
  outline: none;
  box-shadow: 0 0 0 3px var(--color-focus-ring);
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Primary */
.btn-primary {
  background: var(--color-primary);
  color: var(--color-text-inverse);
  border-color: var(--color-primary);
}

.btn-primary:hover:not(:disabled) {
  background: var(--color-primary-hover);
  border-color: var(--color-primary-hover);
}

.btn-primary:active:not(:disabled) {
  background: var(--color-primary-active);
  border-color: var(--color-primary-active);
}

/* Secondary (Outline) */
.btn-secondary {
  background: transparent;
  color: var(--color-text-primary);
  border-color: var(--color-border-default);
}

.btn-secondary:hover:not(:disabled) {
  background: var(--color-hover-overlay);
  border-color: var(--color-border-emphasis);
}

/* Ghost */
.btn-ghost {
  background: transparent;
  color: var(--color-text-secondary);
  border-color: transparent;
}

.btn-ghost:hover:not(:disabled) {
  background: var(--color-hover-overlay);
  color: var(--color-text-primary);
}

/* Danger */
.btn-danger {
  background: var(--color-error);
  color: white;
  border-color: var(--color-error);
}

.btn-danger:hover:not(:disabled) {
  background: #b91c1c;
  border-color: #b91c1c;
}

/* Sizes */
.btn-sm {
  padding: 6px 12px;
  font-size: 13px;
}

.btn-lg {
  padding: 12px 20px;
  font-size: 15px;
}
```

#### Tailwind Implementation

```html
<!-- Primary -->
<button class="inline-flex items-center justify-center gap-2 px-4 py-2.5 text-sm font-medium
               rounded-md bg-primary-600 text-white border border-primary-600
               hover:bg-primary-700 hover:border-primary-700
               focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-500/40
               disabled:opacity-50 disabled:cursor-not-allowed
               dark:bg-primary-500 dark:border-primary-500 dark:hover:bg-primary-400">
  Button
</button>

<!-- Secondary -->
<button class="inline-flex items-center justify-center gap-2 px-4 py-2.5 text-sm font-medium
               rounded-md bg-transparent text-text-primary border border-border-default
               hover:bg-hover-overlay hover:border-border-emphasis
               focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-500/40">
  Button
</button>

<!-- Ghost -->
<button class="inline-flex items-center justify-center gap-2 px-4 py-2.5 text-sm font-medium
               rounded-md bg-transparent text-text-secondary border border-transparent
               hover:bg-hover-overlay hover:text-text-primary
               focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-500/40">
  Button
</button>

<!-- Small variants: add these classes -->
<!-- px-3 py-1.5 text-[13px] -->
```

---

### 4.7 Form Inputs

#### Text Input

```css
.input {
  width: 100%;
  padding: 10px 12px;
  font-size: 14px;
  line-height: 1.5;
  color: var(--color-text-primary);
  background: var(--color-bg-base);
  border: 1px solid var(--color-border-default);
  border-radius: 6px;
  transition: border-color 150ms ease, box-shadow 150ms ease;
}

.input::placeholder {
  color: var(--color-text-disabled);
}

.input:hover:not(:disabled) {
  border-color: var(--color-border-emphasis);
}

.input:focus {
  outline: none;
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px var(--color-focus-ring);
}

.input:disabled {
  background: var(--color-bg-muted);
  cursor: not-allowed;
  opacity: 0.7;
}

/* Select */
.select {
  appearance: none;
  background-image: url("data:image/svg+xml,..."); /* Chevron down */
  background-repeat: no-repeat;
  background-position: right 12px center;
  background-size: 16px;
  padding-right: 40px;
}
```

#### Tailwind Implementation

```html
<input type="text"
       class="w-full px-3 py-2.5 text-sm text-text-primary bg-bg-base
              border border-border-default rounded-md
              placeholder:text-text-disabled
              hover:border-border-emphasis
              focus:outline-none focus:border-primary-600 focus:ring-[3px] focus:ring-primary-500/40
              disabled:bg-bg-muted disabled:opacity-70 disabled:cursor-not-allowed
              dark:bg-surface-dark-muted"
       placeholder="Search...">

<select class="w-full px-3 py-2.5 pr-10 text-sm text-text-primary bg-bg-base
               border border-border-default rounded-md appearance-none
               bg-[url('data:image/svg+xml,...')] bg-no-repeat bg-[right_12px_center] bg-[length:16px]
               hover:border-border-emphasis
               focus:outline-none focus:border-primary-600 focus:ring-[3px] focus:ring-primary-500/40">
  <option>Option 1</option>
</select>
```

---

### 4.8 Theme Toggle Button

#### Design
- **Icon**: Sun for light mode, Moon for dark mode
- **Location**: Bottom of sidebar
- **Behavior**: Click toggles theme, respects system preference on first load

#### Implementation

```html
<button class="flex items-center justify-center w-9 h-9 rounded-md
               bg-transparent text-text-secondary border border-transparent
               hover:bg-hover-overlay hover:text-text-primary
               focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-500/40"
        @click="toggleTheme()"
        :title="isDark ? 'Switch to light mode' : 'Switch to dark mode'">
  <!-- Sun icon (shown in dark mode) -->
  <svg x-show="isDark" class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
          d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z"/>
  </svg>
  <!-- Moon icon (shown in light mode) -->
  <svg x-show="!isDark" class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
          d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z"/>
  </svg>
</button>
```

#### JavaScript Logic

```javascript
// Alpine.js data for theme management
document.addEventListener('alpine:init', () => {
  Alpine.data('themeManager', () => ({
    isDark: false,

    init() {
      // Check localStorage first, then system preference
      const stored = localStorage.getItem('theme');
      if (stored) {
        this.isDark = stored === 'dark';
      } else {
        this.isDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
      }
      this.applyTheme();

      // Listen for system preference changes
      window.matchMedia('(prefers-color-scheme: dark)')
        .addEventListener('change', (e) => {
          if (!localStorage.getItem('theme')) {
            this.isDark = e.matches;
            this.applyTheme();
          }
        });
    },

    toggleTheme() {
      this.isDark = !this.isDark;
      localStorage.setItem('theme', this.isDark ? 'dark' : 'light');
      this.applyTheme();
    },

    applyTheme() {
      document.documentElement.setAttribute('data-theme', this.isDark ? 'dark' : 'light');
    }
  }));
});
```

---

## 5. Responsive Breakpoints

### 5.1 Breakpoint Values

| Token | Width | Target |
|-------|-------|--------|
| `sm` | 640px | Large phones (landscape) |
| `md` | 768px | Tablets |
| `lg` | 1024px | Small laptops |
| `xl` | 1280px | Desktops |
| `2xl` | 1536px | Large desktops |

### 5.2 Layout Behavior

#### Sidebar
| Breakpoint | Behavior |
|------------|----------|
| < 768px | Hidden by default, overlay when toggled |
| >= 768px | Collapsed (icons only) |
| >= 1024px | Expanded (icons + labels) |

#### Content Area
| Breakpoint | Behavior |
|------------|----------|
| < 640px | Full width, minimal padding (16px) |
| >= 640px | Padding 24px |
| >= 1024px | Left margin for sidebar |
| >= 1280px | Max-width constraint (1400px), centered |

#### Dashboard Grid
| Breakpoint | Columns |
|------------|---------|
| < 640px | 1 column |
| >= 640px | 2 columns |
| >= 1024px | 4 columns |

#### Question Options Grid
| Breakpoint | Columns |
|------------|---------|
| < 640px | 1 column |
| >= 640px | 2 columns |

#### Data Tables
| Breakpoint | Behavior |
|------------|----------|
| All | Horizontal scroll wrapper |

### 5.3 Mobile Navigation

```html
<!-- Mobile menu button (shown < 768px) -->
<button class="md:hidden fixed top-4 left-4 z-50 p-2 rounded-md bg-surface-primary
               border border-border-default shadow-md"
        @click="sidebarOpen = !sidebarOpen">
  <svg class="w-5 h-5"><!-- Menu icon --></svg>
</button>

<!-- Sidebar overlay (mobile) -->
<div class="fixed inset-0 bg-black/50 z-30 md:hidden"
     x-show="sidebarOpen"
     @click="sidebarOpen = false"
     x-transition:enter="transition-opacity duration-200"
     x-transition:leave="transition-opacity duration-200">
</div>

<!-- Sidebar with mobile positioning -->
<aside class="fixed left-0 top-0 h-screen z-40
              w-60 transform -translate-x-full md:translate-x-0
              transition-transform duration-200"
       :class="{ 'translate-x-0': sidebarOpen }">
  <!-- Sidebar content -->
</aside>
```

---

## 6. CSS Variable Structure (Complete)

```css
:root {
  /* ============================================
     LIGHT THEME VARIABLES
     ============================================ */

  /* Backgrounds */
  --color-bg-base: #ffffff;
  --color-bg-subtle: #f8fafa;
  --color-bg-muted: #f1f5f5;
  --color-bg-emphasis: #e8eeee;

  /* Surfaces */
  --color-surface-primary: #ffffff;
  --color-surface-secondary: #f8fafa;
  --color-surface-elevated: #ffffff;

  /* Borders */
  --color-border-default: #e2e8e8;
  --color-border-muted: #eef2f2;
  --color-border-emphasis: #cbd5d5;

  /* Text */
  --color-text-primary: #1a2626;
  --color-text-secondary: #4a5858;
  --color-text-muted: #6b7a7a;
  --color-text-disabled: #9ca8a8;
  --color-text-inverse: #ffffff;

  /* Primary (Teal/Cyan) */
  --color-primary: #0891b2;
  --color-primary-hover: #0e7490;
  --color-primary-active: #155e75;
  --color-primary-subtle: #ecfeff;
  --color-primary-muted: #cffafe;

  /* Semantic Colors */
  --color-success: #059669;
  --color-success-subtle: #ecfdf5;
  --color-success-border: #a7f3d0;

  --color-warning: #d97706;
  --color-warning-subtle: #fffbeb;
  --color-warning-border: #fde68a;

  --color-error: #dc2626;
  --color-error-subtle: #fef2f2;
  --color-error-border: #fecaca;

  --color-info: #2563eb;
  --color-info-subtle: #eff6ff;
  --color-info-border: #bfdbfe;

  --color-neutral: #6b7a7a;
  --color-neutral-subtle: #f1f5f5;
  --color-neutral-border: #e2e8e8;

  /* Interactive */
  --color-focus-ring: rgba(8, 145, 178, 0.4);
  --color-hover-overlay: rgba(0, 0, 0, 0.04);
  --color-active-overlay: rgba(0, 0, 0, 0.08);

  /* Shadows */
  --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.05);
  --shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.07), 0 2px 4px -1px rgba(0, 0, 0, 0.04);
  --shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.08), 0 4px 6px -2px rgba(0, 0, 0, 0.04);

  /* Sidebar */
  --sidebar-width-expanded: 240px;
  --sidebar-width-collapsed: 64px;
  --sidebar-bg: #f8fafa;
  --sidebar-border: #e2e8e8;
  --sidebar-item-hover: #e8eeee;
  --sidebar-item-active: #e8eeee;
  --sidebar-item-active-border: #0891b2;

  /* Layout */
  --content-padding: 24px;
  --content-max-width: 1400px;
  --card-border-radius: 8px;
  --input-border-radius: 6px;
  --btn-border-radius: 6px;

  /* Typography */
  --font-sans: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  --font-mono: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace;

  /* Transitions */
  --transition-fast: 150ms ease;
  --transition-normal: 200ms ease;
  --transition-slow: 300ms ease;
}

[data-theme="dark"] {
  /* ============================================
     DARK THEME OVERRIDES
     ============================================ */

  /* Backgrounds */
  --color-bg-base: #0f1414;
  --color-bg-subtle: #161c1c;
  --color-bg-muted: #1e2626;
  --color-bg-emphasis: #283030;

  /* Surfaces */
  --color-surface-primary: #161c1c;
  --color-surface-secondary: #1e2626;
  --color-surface-elevated: #1e2626;

  /* Borders */
  --color-border-default: #2d3838;
  --color-border-muted: #242e2e;
  --color-border-emphasis: #3d4a4a;

  /* Text */
  --color-text-primary: #f0f4f4;
  --color-text-secondary: #a8b8b8;
  --color-text-muted: #7a8a8a;
  --color-text-disabled: #4a5858;
  --color-text-inverse: #0f1414;

  /* Primary (Teal/Cyan - brighter for dark) */
  --color-primary: #22d3ee;
  --color-primary-hover: #67e8f9;
  --color-primary-active: #a5f3fc;
  --color-primary-subtle: #164e63;
  --color-primary-muted: #155e75;

  /* Semantic Colors */
  --color-success: #34d399;
  --color-success-subtle: #064e3b;
  --color-success-border: #065f46;

  --color-warning: #fbbf24;
  --color-warning-subtle: #78350f;
  --color-warning-border: #92400e;

  --color-error: #f87171;
  --color-error-subtle: #7f1d1d;
  --color-error-border: #991b1b;

  --color-info: #60a5fa;
  --color-info-subtle: #1e3a5f;
  --color-info-border: #1e40af;

  --color-neutral: #a8b8b8;
  --color-neutral-subtle: #1e2626;
  --color-neutral-border: #2d3838;

  /* Interactive */
  --color-focus-ring: rgba(34, 211, 238, 0.4);
  --color-hover-overlay: rgba(255, 255, 255, 0.04);
  --color-active-overlay: rgba(255, 255, 255, 0.08);

  /* Shadows (subtle in dark mode) */
  --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.3);
  --shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.4), 0 2px 4px -1px rgba(0, 0, 0, 0.3);
  --shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.4), 0 4px 6px -2px rgba(0, 0, 0, 0.3);

  /* Sidebar */
  --sidebar-bg: #161c1c;
  --sidebar-border: #2d3838;
  --sidebar-item-hover: #1e2626;
  --sidebar-item-active: #1e2626;
  --sidebar-item-active-border: #22d3ee;
}
```

---

## 7. Accessibility Checklist

### 7.1 Color Contrast
- All text meets WCAG 2.1 AA minimum (4.5:1 for normal text, 3:1 for large text)
- Interactive elements have 3:1 contrast against backgrounds
- Focus indicators are clearly visible in both themes

### 7.2 Focus Management
- All interactive elements have visible focus states
- Focus ring uses `box-shadow` (not `outline`) for consistency
- Tab order is logical and follows visual layout
- Skip links provided for keyboard navigation

### 7.3 Screen Reader Support
- Semantic HTML elements used (nav, main, article, etc.)
- ARIA labels on icon-only buttons
- Live regions for dynamic content updates (HTMX)
- Proper heading hierarchy (h1 > h2 > h3)

### 7.4 Motion & Animation
- All animations respect `prefers-reduced-motion`
- Transitions are subtle (150-200ms)
- No essential information conveyed through motion alone

### 7.5 Interactive Elements
- Touch targets minimum 44x44px on mobile
- Buttons have descriptive text or aria-label
- Form inputs have associated labels
- Error states are communicated beyond color (icons, text)

---

## 8. Implementation Notes

### 8.1 File Structure

```
src/web/
  static/
    css/
      main.css          # Tailwind imports + custom properties
      components.css    # Component-specific styles (if needed)
    js/
      theme.js          # Theme toggle logic
      app.js            # Alpine.js initialization
  templates/
    base.html           # Layout with sidebar
    components/
      sidebar.html      # Sidebar partial
      stat-card.html    # Dashboard card partial
      question-card.html
      data-table.html
```

### 8.2 Tailwind Configuration

```javascript
// tailwind.config.js
module.exports = {
  content: ['./src/web/templates/**/*.html'],
  darkMode: ['class', '[data-theme="dark"]'],
  theme: {
    extend: {
      colors: {
        // Map CSS variables for Tailwind
        'bg-base': 'var(--color-bg-base)',
        'bg-subtle': 'var(--color-bg-subtle)',
        'bg-muted': 'var(--color-bg-muted)',
        'bg-emphasis': 'var(--color-bg-emphasis)',
        'surface-primary': 'var(--color-surface-primary)',
        'border-default': 'var(--color-border-default)',
        'border-muted': 'var(--color-border-muted)',
        'text-primary': 'var(--color-text-primary)',
        'text-secondary': 'var(--color-text-secondary)',
        'text-muted': 'var(--color-text-muted)',
        'hover-overlay': 'var(--color-hover-overlay)',
        // ... etc
      },
      boxShadow: {
        'sm': 'var(--shadow-sm)',
        'md': 'var(--shadow-md)',
        'lg': 'var(--shadow-lg)',
      },
      fontFamily: {
        sans: 'var(--font-sans)',
        mono: 'var(--font-mono)',
      },
      spacing: {
        'sidebar-expanded': 'var(--sidebar-width-expanded)',
        'sidebar-collapsed': 'var(--sidebar-width-collapsed)',
      },
      maxWidth: {
        'content': 'var(--content-max-width)',
      },
    },
  },
  plugins: [],
}
```

### 8.3 Build Process

```bash
# Install dependencies
npm install -D tailwindcss

# Build CSS (development)
npx tailwindcss -i ./src/web/static/css/input.css -o ./src/web/static/css/main.css --watch

# Build CSS (production)
npx tailwindcss -i ./src/web/static/css/input.css -o ./src/web/static/css/main.css --minify
```

### 8.4 HTMX Integration Notes

- HTMX responses should return partial HTML that matches the design system
- Use `hx-swap="innerHTML"` for content updates within existing containers
- Add `aria-live="polite"` to containers that receive dynamic content
- Include loading states using `htmx-request` class hooks

---

## 9. Visual Reference Summary

### Color Reference (Quick)

| Token | Light | Dark |
|-------|-------|------|
| Background | #ffffff | #0f1414 |
| Surface | #f8fafa | #161c1c |
| Border | #e2e8e8 | #2d3838 |
| Text Primary | #1a2626 | #f0f4f4 |
| Text Secondary | #4a5858 | #a8b8b8 |
| Primary | #0891b2 | #22d3ee |
| Success | #059669 | #34d399 |
| Warning | #d97706 | #fbbf24 |
| Error | #dc2626 | #f87171 |

### Spacing Reference (Quick)

| Use Case | Value |
|----------|-------|
| Component gap | 16px |
| Card padding | 20px |
| Input padding | 10px 12px |
| Button padding | 10px 16px |
| Section margin | 24-32px |

### Typography Reference (Quick)

| Element | Size | Weight |
|---------|------|--------|
| Page title | 24px | 600 |
| Section header | 20px | 600 |
| Card title | 18px | 500 |
| Body text | 14-15px | 400 |
| Labels/Badges | 12-13px | 500 |

---

## 10. Implementation Checklist

### Phase 1: Foundation Setup
- [ ] Install Tailwind CSS (`npm install -D tailwindcss`)
- [ ] Create `tailwind.config.js` with custom theme extensions
- [ ] Create `src/web/static/css/input.css` with CSS custom properties
- [ ] Set up build script in `package.json`
- [ ] Add Google Fonts link (optional: Inter) or use system fonts

### Phase 2: Base Layout
- [ ] Update `base.html` with new structure (sidebar + main content)
- [ ] Create sidebar partial (`partials/sidebar.html`)
- [ ] Implement theme toggle with localStorage persistence
- [ ] Add system preference detection script
- [ ] Test responsive sidebar behavior (collapsed/expanded/overlay)

### Phase 3: Components
- [ ] Style buttons (primary, secondary, ghost variants)
- [ ] Style form inputs (text, search, select)
- [ ] Create stat cards for dashboard
- [ ] Style data tables with sticky headers
- [ ] Create question card component with muted badges
- [ ] Style pagination controls
- [ ] Style breadcrumb navigation

### Phase 4: Page Updates
- [ ] Convert Dashboard (`index.html`)
- [ ] Convert Tables list (`tables.html`)
- [ ] Convert Table browser (`table_browse.html`)
- [ ] Convert Record detail (`record.html`)
- [ ] Convert Questions page (`questions.html`)
- [ ] Update all partials for HTMX responses

### Phase 5: Polish & Testing
- [ ] Test dark/light mode in all pages
- [ ] Verify responsive breakpoints (mobile, tablet, desktop)
- [ ] Run accessibility audit (contrast, focus states, ARIA)
- [ ] Test keyboard navigation
- [ ] Cross-browser testing (Chrome, Firefox, Safari)
- [ ] Remove old Pico CSS references

---

## 11. Migration Notes

### Removing Pico CSS

1. Remove from `base.html`:
```html
<!-- REMOVE THIS LINE -->
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@picocss/pico@2/css/pico.min.css">
```

2. Replace `data-theme="light"` attribute handling (Pico uses same pattern, compatible)

3. Remove `role="button"` from links (use proper button classes instead)

4. Replace Pico's `.grid` with Tailwind grid utilities

5. Remove `custom.css` or merge any needed styles into new system

### Key Class Mappings (Pico to Tailwind)

| Pico | Tailwind Equivalent |
|------|---------------------|
| `container` | `max-w-content mx-auto px-6` |
| `container-fluid` | `w-full px-6` |
| `article` | `card` (custom component class) |
| `.grid` | `grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4` |
| `.outline` | `btn-secondary` |
| `.secondary` | `text-text-secondary` |
| `mark` | `badge-neutral` |

---

*Document Version: 1.1*
*Last Updated: 2026-01-19*
*Author: UI Designer Agent*
