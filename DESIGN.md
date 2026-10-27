---
name: Anomaly
description: A filter drawn on chart paper. Records flow from sources through detectors, and a red pen circles the few that come out as leads.
colors:
  paper: "#F5F6F0"
  paper-2: "#ECEEE5"
  paper-3: "#E2E5DA"
  grid: "rgba(28, 115, 80, 0.10)"
  grid-major: "rgba(28, 115, 80, 0.22)"
  ink: "#161B22"
  ink-2: "#434C55"
  ink-3: "#626B73"
  rule: "rgba(22, 27, 34, 0.14)"
  rule-2: "rgba(22, 27, 34, 0.26)"
  blue: "#2546B5"
  blue-tint: "rgba(37, 70, 181, 0.09)"
  green: "#1C7350"
  green-tint: "rgba(28, 115, 80, 0.10)"
  red: "#D42A3C"
  red-tint: "rgba(212, 42, 60, 0.09)"
typography:
  display:
    fontFamily: "'Martian Mono', ui-monospace, 'SF Mono', Menlo, monospace"
    fontSize: "clamp(2.1rem, 4vw, 3.4rem)"
    fontWeight: 560
    lineHeight: 1.02
    letterSpacing: "-0.045em"
    fontVariation: "'wdth' 112.5"
  headline:
    fontFamily: "'Martian Mono', ui-monospace, 'SF Mono', Menlo, monospace"
    fontSize: "clamp(1.6rem, 3vw, 2.35rem)"
    fontWeight: 560
    lineHeight: 1.12
    letterSpacing: "-0.035em"
    fontVariation: "'wdth' 112.5"
  title:
    fontFamily: "'Martian Mono', ui-monospace, 'SF Mono', Menlo, monospace"
    fontSize: "1.3rem"
    fontWeight: 600
    letterSpacing: "-0.02em"
    fontVariation: "'wdth' 112.5"
  subtitle:
    fontFamily: "'Martian Mono', ui-monospace, 'SF Mono', Menlo, monospace"
    fontSize: "0.92rem"
    fontWeight: 600
    letterSpacing: "-0.005em"
    fontVariation: "'wdth' 100"
  body:
    fontFamily: "'Martian Mono', ui-monospace, 'SF Mono', Menlo, monospace"
    fontSize: "0.94rem"
    fontWeight: 360
    lineHeight: 1.7
    fontVariation: "'wdth' 87.5"
    fontFeature: "'tnum'"
  small:
    fontFamily: "'Martian Mono', ui-monospace, 'SF Mono', Menlo, monospace"
    fontSize: "0.8rem"
    fontWeight: 360
    lineHeight: 1.6
    fontVariation: "'wdth' 87.5"
  label:
    fontFamily: "'Martian Mono', ui-monospace, 'SF Mono', Menlo, monospace"
    fontSize: "0.76rem"
    fontWeight: 360
    letterSpacing: "0.06em"
    fontVariation: "'wdth' 87.5"
rounded:
  code: "4px"
  tag: "5px"
  control: "7px"
  tile: "8px"
  panel: "10px"
  frame: "12px"
  pill: "999px"
spacing:
  wrap: "min(100% - 2.5rem, 74rem)"
  grid-minor: "10px"
  grid-major: "50px"
  section: "clamp(4.5rem, 10vw, 7.5rem)"
components:
  button-primary:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.paper}"
    rounded: "{rounded.pill}"
    padding: "0 1.5rem"
    height: "3.1rem"
  button-primary-sm:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.paper}"
    rounded: "{rounded.pill}"
    padding: "0 1.15rem"
    height: "2.6rem"
  button-primary-hover:
    backgroundColor: "#000000"
  icon-button:
    textColor: "{colors.ink}"
    rounded: "{rounded.pill}"
    size: "2.6rem"
  icon-button-hover:
    backgroundColor: "{colors.paper-2}"
  chip:
    textColor: "{colors.ink-2}"
    rounded: "{rounded.pill}"
    padding: "0 0.85rem"
    height: "2.25rem"
  chip-selected:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.paper}"
  search-input:
    backgroundColor: "#FFFFFF"
    textColor: "{colors.ink}"
    rounded: "{rounded.frame}"
    padding: "0 1.2rem 0 3.1rem"
    height: "3.6rem"
  command-row:
    backgroundColor: "{colors.paper-2}"
    textColor: "{colors.ink}"
    rounded: "{rounded.panel}"
    padding: "0.55rem 0.55rem 0.55rem 1.1rem"
  copy-button:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink-2}"
    rounded: "{rounded.control}"
    size: "2.4rem"
  readout:
    backgroundColor: "{colors.paper-2}"
    textColor: "{colors.ink-2}"
    rounded: "{rounded.panel}"
    padding: "1rem 1.2rem"
---

# Design System: Anomaly

## Overview

**Creative North Star: "The Chart-Paper Filter"**

Anomaly is drawn on cool chart paper with a green engineering grid. Records travel across it as blue dots, pass through green detector gates, and the few that do not fit are caught and circled in red pen. Everything else on the page is quiet ink on paper, so the three data colours carry all the meaning.

One variable monospace family does every job. Its width axis separates the voices: wide (112.5) for headlines, normal (100) for small titles, condensed (87.5) for reading and measurement. The page is light, flat and calm: no shadows for lift, hairline inset rules, generous section spacing, and soft-cornered paper panels (`paper-2`) for anything that holds a readout.

Anomaly has its own look, separate from Buried Signals; it presents as a Spotlight plugin.

**Key Characteristics:**
- Cool chart paper with a two-level green grid on diagram surfaces only.
- Martian Mono only; width axis, not a second family, makes hierarchy.
- Colour is semantic: blue = data and sources, green = detectors, red = leads.
- The hand-drawn red ring is the signature mark.
- Pill buttons and a round icon button; everything else flat.

## Colors

Ink on cool paper, with three semantic pens.

### Primary
- **Source Blue** (`blue`): records in flight, queryable sources, source edges in the domain diagram, links that expand the catalogue, focus rings, caret and text selection.

### Secondary
- **Detector Green** (`green`): detector gates on the bench, detector edges and markers in the diagram, detector tags in the catalogue, the copy-done tick. Also the grid colour at low alpha (`grid`, `grid-major`).

### Tertiary
- **Lead Red** (`red`): caught records, the leads tray, the leads tally, the Lead step, the red ring on the headline phrase and on Install hover, the gate flash when a detector catches a record.

### Neutral
- **Chart Paper** (`paper`): page background and diagram ground.
- **Paper Fold** (`paper-2`): readouts, command rows, open catalogue rows, selected steps, hover fills.
- **Paper Crease** (`paper-3`): deepest paper tone; reserved.
- **Ink** (`ink`): text, primary buttons, selected chips, the domain hub outline.
- **Ink Soft** (`ink-2`): ledes, intros, secondary text.
- **Ink Faint** (`ink-3`): captions, metadata, axis and column labels.
- **Rule / Rule Strong** (`rule`, `rule-2`): hairlines, inset outlines, underline colour.

### Named Rules
**The Three Pens Rule.** Blue, green and red each mean one thing: data, detectors, leads. Never use one of them for decoration or for a different meaning.

**The Red Is Earned Rule.** Red marks leads and the ring that circles them, nothing else. No red errors, badges or emphasis.

## Typography

**Display Font:** Martian Mono, width 112.5 (fallback ui-monospace, SF Mono, Menlo)
**Body Font:** Martian Mono, width 87.5
**Label/Mono Font:** same family

**Character:** A measurement voice. Wide and tight-tracked at the top, condensed and light (360) for reading, tabular figures throughout so counts line up.

### Hierarchy
- **Display** (560, `clamp(2.1rem, 4vw, 3.4rem)`, 1.02): the hero headline only; balanced wrapping.
- **Headline** (560, `clamp(1.6rem, 3vw, 2.35rem)`, 1.12): section headings, max 24ch.
- **Title** (600, 1.3rem): the hero tagline.
- **Subtitle** (600, 0.92rem, width 100): step names and small headings.
- **Body** (360, 0.94rem, 1.7): ledes up to 46ch, intros up to 66ch.
- **Small** (0.78–0.84rem): captions, catalogue rows, readouts, notes up to 78ch.
- **Label** (0.76rem, 0.06em, uppercase): catalogue column headers and diagram axis labels (SOURCES, DETECTORS, LEADS) only.

### Named Rules
**The Width Is The Hierarchy Rule.** Change the width axis and weight to make rank; never add a second family.

**The Labels Name Axes Rule.** Uppercase tracked text appears only as a column or axis label attached to the data it names, never as a section kicker above a heading.

## Layout

A single centred column (`wrap`: up to 74rem with 1.25rem gutters). The hero is two columns (1.4fr / 1fr, 4rem gap), stacking under 960px. The filter bench is full-bleed between strong rules, 290–430px tall. Sections open with `section` spacing; the footer sits further away. The six steps sit in a six-column row (two columns under 760px). The catalogue is a ledger of hairline-ruled rows (five columns, three under 960px, two under 760px). Under 760px the domain diagram becomes a stacked list and the step route line hides. Chip rows scroll horizontally on mobile instead of wrapping.

Grid-drawn surfaces (bench, domain frame) use a 10px minor and 50px major grid; drawings snap to it.

## Elevation & Depth

Flat. Depth comes from tone (`paper` vs `paper-2`) and 1px inset outlines (`box-shadow: inset 0 0 0 1px` with `rule` or `rule-2`), never from cast shadows.

### Named Rules
**The Paper Lies Flat Rule.** No drop shadows. Outlines are inset hairlines; emphasis is a tone shift.

## Shapes

Soft corners scaled to size: 4px code, 5px tags, 7px small controls, 8px step tiles, 10px panels and command rows, 12px frames and the search field. Actions are full pills; the GitHub button is a circle. Data marks are geometric: blue filled dots for records, dashed circles for catalogued sources, small rounded squares for detectors, and a loose hand-drawn ellipse (the ring) around anything that becomes a lead.

## Components

### Buttons
- **Shape:** full pill (`pill`).
- **Primary:** ink fill, paper text, 560 weight, trailing arrow; 3.1rem tall, a 2.6rem small variant in the nav.
- **Hover / Focus:** fill deepens; the arrow nudges 3px right; a red ring draws itself around the button (stroke-dashoffset, 0.9s, `cubic-bezier(0.16, 1, 0.3, 1)`). Focus also gets the global 2px blue outline.
- **Text link action:** "Open Spotlight": underlined ink text with the same arrow nudge, no fill.

### Icon button (GitHub)
- Round 2.6rem button with a 1px inset `rule-2` outline and an 18px inline SVG; hover fills `paper-2` and darkens the outline to ink.

### Chips
- **Style:** pill, transparent, inset `rule` outline, `ink-2` text, optional count at 0.7 opacity.
- **State:** selected or pressed fills ink with paper text. Used for domain picks, catalogue tabs and filters.

### Inputs / Fields
- **Search:** 3.6rem tall, 12px radius, inset `rule-2` outline, leading search icon in `ink-3`.
- **Focus:** 1.5px blue inset outline plus a 4px `blue-tint` halo.

### Catalogue ledger
- Hairline-ruled rows; hover tints the row; an expanded row and its detail panel sit on `paper-2`. Status tags lead with a 7px marker: blue filled dot (queryable), dashed ring (catalogued), green square (detector).

### Readouts and command rows
- `paper-2` panels with 10px corners. Commands show a small label, the command in ink, and a 7px-radius copy button that turns green when copied.

### Filter bench (signature)
- A full-width chart-paper canvas: four blue source tables, three green detector gates with tick marks, a white leads tray. Blue dots stream left to right; dots that clear the last gate fade to grey; caught dots turn red, get ringed, and stack in the tray as numbered leads. A tally and a Pause control sit under it. Reduced motion stops the animation.

### Domain diagram
- On grid paper: sources on the left (blue solid edges, grey dashed for catalogued), an ink-outlined hub naming the domain and its tables, detectors on the right in green.

### Navigation
- Logo mark (a trace with a red ring) and wordmark left; round GitHub button and small Install pill right. No menu bar.

## Do's and Don'ts

### Do:
- **Do** keep blue for data, green for detectors and red for leads, everywhere including drawings.
- **Do** use the red ring to mark a lead or the single primary action's hover.
- **Do** make hierarchy with Martian Mono's width axis (112.5 display, 100 titles, 87.5 body).
- **Do** draw diagrams on the 10px / 50px green grid and snap marks to it.
- **Do** separate surfaces with `paper-2` tone and inset hairlines.

### Don't:
- **Don't** add a second typeface or a system display face.
- **Don't** use red for errors, warnings, badges or decorative emphasis.
- **Don't** add cast drop shadows or hard offset shadows.
- **Don't** put uppercase tracked kickers above headings.
- **Don't** put the grid behind running text; it belongs to diagram surfaces.
