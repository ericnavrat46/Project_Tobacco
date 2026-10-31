# Taste Skill - Frontend Design Rules & Anti-Slop Guidelines
# (Adapted from Leonxlnx/taste-skill for Industrial IoT & Tobacco Monitoring)

## 1. Core Philosophy: Anti-Slop & Subject-First
Web interfaces must NOT look like generic AI-generated templates ("AI slop": purple gradient blobs, floating cards with glowing drop-shadows, repetitive 3-column layouts, icons in tinted circles).
Design choices must originate from the **subject itself**:
- **Domain**: Industrial Agriculture, Tobacco Processing & Gudang Curing, High-Precision Telemetry & Sorting.
- **Vibe / Aesthetic**: *High-End Industrial Workstation & Botanical Craft*. Tactile, functional, precise, durable, confident.
- **Palette**: Warm Tobacco Earth (`#b45309`, `#78350f`), Aged Amber (`#d97706`), Warm Muted Paper/Cream (`#fbfbfa` / `#f4f3ef`), Deep Industrial Charcoal/Slate (`#121316`, `#1a1c20`), Brass & Muted Olive accents.

---

## 2. App Screen & Dashboard House Rules

### A. Colour Goes on Data, Not Chrome
- Saturated color pixels should account for **< 5% of the screen**.
- Never put brand/neon gradients on backgrounds, cards, or generic buttons.
- Color indicates **state and decision** (normal, warning, danger, leaf quality grade), not decorative fluff.
- Primary buttons and active tabs use solid, confident neutrals (deep slate/charcoal or warm ink), not glowing gradients.

### B. KPIs: Typography & Value First
- **No icons inside tinted circles** or colored rounded boxes on every KPI tile.
- Numbers are displayed prominently in clean, tabular figures (`font-variant-numeric: tabular-nums` or dedicated clean monospaced font for telemetry).
- Labels sit above or beside values in compact 11–13px subdued tone, sentence case.
- Clear units (e.g. `°C`, `% RH`, `ppm`) styled cleanly beside or beneath the numerals.

### C. Flat, Tactile Surfaces (No Floaty Shadows)
- Separate cards and panels using **1px hairline borders** (`rgba(0,0,0,0.08)` in light mode, `rgba(255,255,255,0.08)` in dark mode) or subtle 1-step tone shifts.
- Eliminate heavy muddy blur shadows (`box-shadow: 0 10px 25px rgba(...)`). Resting cards should feel physically machined and stable.
- Tight, disciplined border-radii (`6px` to `10px`), avoiding overly bubbly, cartoonish rounded corners (`20px+`).

### D. Data Visualizations & Charts
- Minimalist chrome: faint horizontal gridlines (3–5 lines max), no vertical gridline clutter.
- Single series charts do NOT need redundant legends.
- Smooth straight/subtle curves, flat opacity fills (10–14%) instead of multi-color rainbow gradients.
- Donut/pie charts use thin, elegant rings with clean tabular legends, not bloated colored circles.

### E. Tables & Telemetry Logs
- Clean row borders (1px hairline), NO alternating zebra stripes.
- Numeric columns right-aligned with fixed decimal points.
- Status chips: pale, desaturated tint with dark crisp text, never eye-burning saturated badges with white text.

### F. Typography Hierarchy
- Display / Headers: Confident, editorial, legible (e.g., Plus Jakarta Sans / Syne / Space Grotesk).
- Telemetry & Data: Monospace / Tabular numbers (e.g., JetBrains Mono / Space Mono / Roboto Mono).
- No generic emoji in titles, headers, or status indicators.
