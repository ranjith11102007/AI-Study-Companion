---
name: Academic Intelligence
colors:
  surface: '#f8f9ff'
  surface-dim: '#cbdbf5'
  surface-bright: '#f8f9ff'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#eff4ff'
  surface-container: '#e5eeff'
  surface-container-high: '#dce9ff'
  surface-container-highest: '#d3e4fe'
  on-surface: '#0b1c30'
  on-surface-variant: '#464554'
  inverse-surface: '#213145'
  inverse-on-surface: '#eaf1ff'
  outline: '#767586'
  outline-variant: '#c7c4d7'
  surface-tint: '#494bd6'
  primary: '#4648d4'
  on-primary: '#ffffff'
  primary-container: '#6063ee'
  on-primary-container: '#fffbff'
  inverse-primary: '#c0c1ff'
  secondary: '#565e74'
  on-secondary: '#ffffff'
  secondary-container: '#dae2fd'
  on-secondary-container: '#5c647a'
  tertiary: '#006c49'
  on-tertiary: '#ffffff'
  tertiary-container: '#00885d'
  on-tertiary-container: '#000703'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#e1e0ff'
  primary-fixed-dim: '#c0c1ff'
  on-primary-fixed: '#07006c'
  on-primary-fixed-variant: '#2f2ebe'
  secondary-fixed: '#dae2fd'
  secondary-fixed-dim: '#bec6e0'
  on-secondary-fixed: '#131b2e'
  on-secondary-fixed-variant: '#3f465c'
  tertiary-fixed: '#6ffbbe'
  tertiary-fixed-dim: '#4edea3'
  on-tertiary-fixed: '#002113'
  on-tertiary-fixed-variant: '#005236'
  background: '#f8f9ff'
  on-background: '#0b1c30'
  surface-variant: '#d3e4fe'
typography:
  display:
    fontFamily: Plus Jakarta Sans
    fontSize: 48px
    fontWeight: '700'
    lineHeight: 56px
    letterSpacing: -0.03em
  display-mobile:
    fontFamily: Plus Jakarta Sans
    fontSize: 32px
    fontWeight: '700'
    lineHeight: 40px
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Plus Jakarta Sans
    fontSize: 36px
    fontWeight: '700'
    lineHeight: 44px
    letterSpacing: -0.025em
  headline-lg-mobile:
    fontFamily: Plus Jakarta Sans
    fontSize: 26px
    fontWeight: '600'
    lineHeight: 34px
    letterSpacing: -0.02em
  headline-md:
    fontFamily: Plus Jakarta Sans
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
    letterSpacing: -0.015em
  headline-sm:
    fontFamily: Plus Jakarta Sans
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
    letterSpacing: -0.01em
  body-lg:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 26px
  body-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 22px
  body-sm:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 18px
  label-lg:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '600'
    lineHeight: 20px
    letterSpacing: 0.01em
  label-md:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '600'
    lineHeight: 16px
    letterSpacing: 0.02em
  label-sm:
    fontFamily: Inter
    fontSize: 11px
    fontWeight: '700'
    lineHeight: 14px
    letterSpacing: 0.04em
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  gutter: 1.5rem
  gutter-mobile: 1rem
  margin: 2rem
  margin-mobile: 1rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 1rem
  space-lg: 1.5rem
  space-xl: 2.5rem
---

## Brand & Style
The brand bridges rigorous academic discipline with cutting-edge artificial intelligence. It targets ambitious university students, researchers, and lifelong self-directed learners who demand precision, clarity, and intellectual focus. 

The aesthetic fuses modern high-tech SaaS with refined collegiate editorial design. Interfaces are structured, clean, and dense with utility, avoiding unnecessary novelty in favor of cognitive ease. The visual tone evokes confidence, mastery, and technological poise—distilling complex multi-modal study materials into crisp, scannable, high-contrast modules.

## Colors
The palette pairs an authoritative slate-900 foundation with electric, forward-leaning academic accents:

- **Primary (`#6366F1`)**: Indigo / Violet. Drives focused primary actions, active navigation states, generative AI status indicators, and critical focus triggers.
- **Secondary (`#0F172A`)**: Deep Slate. Used for high-contrast architectural framing, authoritative display text, headers, and structural sidebars.
- **Tertiary (`#10B981`)**: Emerald. Explicitly designated for academic mastery, completed milestones, verified answers, and retention streaks.
- **Supportive Accents**:
  - **Attention / Review (`#F59E0B`)**: Amber for spaced-repetition prompts, low-confidence warnings, and upcoming deadlines.
  - **Alert / Remediation (`#EF4444`)**: Rose for quiz corrections, prerequisite blockers, and system exceptions.
- **Neutral Palette (`#64748B`, `#F8FAFC`, `#FFFFFF`)**: Pure crisp white surfaces stacked against cool slate grounds (`#F1F5F9` canvas, `#0F172A` high-contrast dark accents).

## Typography
Plus Jakarta Sans provides high-clarity structural weight for headlines and section dividers, offering modern geometric curves with collegiate authority. Inter manages body content, metadata, data-heavy syllabi, and interactive controls with neutral, metric-optimized legibility.

Letter spacing is drawn tightly on headlines to impart rigor and density, while labels and metadata leverage deliberate uppercase or positive tracking for high-speed scanning during intense study sessions.

## Layout & Spacing
The layout implements a fixed-max-width 12-column grid system (capped at 1440px) pinned against responsive margins. 

- **Desktop (1024px+)**: 12 columns with 24px gutters and 32px canvas margins. Study workspaces allow an asymmetric 3-column setup: persistent navigation/syllabus rail (col-span 3), dynamic workspace/reading area (col-span 6), and active AI tutor/quiz telemetry sidebar (col-span 3).
- **Tablet (768px - 1023px)**: 8 columns with 16px gutters and 24px margins. Sidebar panels collapse into bottom drawers or slide-in sheets.
- **Mobile (<768px)**: 4 columns with 16px gutters and 16px margins. Content stacks vertically with sticky bottom actionbars for ongoing flashcard reviews and AI dialogue prompts.

## Elevation & Depth
Visual hierarchy relies primarily on crisp tonal stacking and architectural surface divisions rather than dramatic drop shadows:

- **Surface Tiers**: Base canvas sits on `#F8FAFC`. Neutral cards rest on pure `#FFFFFF`. Sub-panels and nested modules use `#F1F5F9` fills.
- **Outlines**: Every card and floating module features a sharp, 1px low-contrast border (`#E2E8F0` or `#CBD5E1`), ensuring structural separation under ambient light.
- **Ambient Shadow System**: Used strictly for elevated, detached elements like flashcards, modal dialogues, and active dropdowns. Shadows carry a soft indigo tint (`rgba(15, 23, 42, 0.04)` to `rgba(99, 102, 241, 0.08)`) with wide blurs (12px to 24px) and zero harsh black values.
- **AI Focus State**: Active generative panels use a subtle 1px border shift to primary indigo (`#6366F1`) paired with a faint glow (`0 0 0 3px rgba(99, 102, 241, 0.12)`).

## Shapes
A roundedness level of `2` provides standard radii of 0.5rem (8px), scaling to 1rem (16px) on cards and containers. This balance keeps interfaces structural and disciplined without feeling abrasive. 

Interactive tags, subject pills, mastery badges, and user avatars intentionally depart from the base shape into full pill radii (`rounded-full`) to immediately distinguish contextual metadata from primary interface containers.

## Components

### Buttons
- **Primary**: Solid indigo (`#6366F1`) fill, pure white text, 8px radius, medium weight. Subtle scale transition on hover with deepened indigo tone (`#4F46E5`).
- **Secondary**: Slate-900 (`#0F172A`) solid fill with white text for decisive academic actions (e.g., "Submit Exam", "Generate Flashcards").
- **Ghost / Outline**: Pure white background, 1px `#CBD5E1` border, slate-700 text. Hover activates `#F8FAFC` background.

### Chips & Badges
- Fully rounded pills (`rounded-full`) with compact padding (`py-1 px-3`).
- **Mastery Status**: Pale emerald background (`#ECFDF5`), deep emerald text (`#047857`), 1px `#A7F3D0` outline.
- **AI Status**: Pale indigo background (`#EEF2FF`), primary indigo text (`#4F46E5`), accompanied by a 6px pulsing dot indicator.

### Flashcard & Study Containers
- Crisp white canvas, 16px corner radius, 1px `#E2E8F0` outline, soft 8px ambient drop shadow.
- High-contrast header with 12px label tracking. Interactive flip zones use high-clarity typography with center-aligned display sizing.

### Form Inputs & Query Fields
- 8px radius, white surface, 1px `#CBD5E1` border, 12px vertical padding. Focus transitions to an indigo border with a 3px diffused outer halo (`rgba(99, 102, 241, 0.15)`). Monospaced metadata or character counts sit inline on label-sm typography.

### Checkboxes & Mastery Radios
- Square 4px rounded checkboxes; circular radios. Active states use solid `#6366F1` with white iconography. Multi-choice diagnostic options highlight with a subtle `#EEF2FF` wash across the entire row when selected.

### Academic Telemetry Panels
- Miniaturized data displays tracking spaced-repetition retention curves, streak tallies, and chapter mastery. Formatted with slate-900 counters, `#64748B` micro-labels, and `#10B981` progress bars with rounded terminal ends.