---
name: Anomaly
description: A station departures board for data, where a record that doesn't fit flips to LEAD.
colors:
  housing-charcoal: "#16191B"
  board-housing: "#1B1F21"
  led-cell: "#0D0F10"
  cell-head: "#111415"
  cell-line: "#22272A"
  housing-edge: "#2A3033"
  field-edge: "#333A3E"
  signal-amber: "#D4A853"
  lead-amber-hot: "#F2C266"
  amber-tint: "rgba(212, 168, 83, 0.15)"
  amber-edge: "rgba(212, 168, 83, 0.4)"
  cream: "#F5F2ED"
  cream-muted: "rgba(245, 242, 237, 0.66)"
  cream-faint: "rgba(245, 242, 237, 0.56)"
  cream-rule: "rgba(245, 242, 237, 0.13)"
  queryable-teal: "#7DB1AE"
  teal-tint: "rgba(91, 138, 138, 0.28)"
typography:
  display:
    fontFamily: "'Space Grotesk', system-ui, sans-serif"
    fontSize: "clamp(2.9rem, 6.4vw, 5.6rem)"
    fontWeight: 600
    lineHeight: 0.95
    letterSpacing: "-0.035em"
  headline:
    fontFamily: "'Space Grotesk', system-ui, sans-serif"
    fontSize: "clamp(2rem, 4.2vw, 3.3rem)"
    fontWeight: 600
    lineHeight: 1.02
    letterSpacing: "-0.03em"
  title:
    fontFamily: "'Space Grotesk', system-ui, sans-serif"
    fontSize: "1.22rem"
    fontWeight: 600
    letterSpacing: "-0.01em"
  lede:
    fontFamily: "'Space Grotesk', system-ui, sans-serif"
    fontSize: "1.12rem"
    fontWeight: 400
    lineHeight: 1.55
  body:
    fontFamily: "'Space Grotesk', system-ui, sans-serif"
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.6
  body-small:
    fontFamily: "'Space Grotesk', system-ui, sans-serif"
    fontSize: "0.92rem"
    fontWeight: 400
    lineHeight: 1.5
  label:
    fontFamily: "'Space Mono', ui-monospace, monospace"
    fontSize: "0.78rem"
    fontWeight: 400
    lineHeight: 1
    letterSpacing: "0.12em"
  label-column:
    fontFamily: "'Space Mono', ui-monospace, monospace"
    fontSize: "0.66rem"
    fontWeight: 400
    lineHeight: 1
    letterSpacing: "0.16em"
  code:
    fontFamily: "'Space Mono', ui-monospace, monospace"
    fontSize: "0.88rem"
    fontWeight: 400
    lineHeight: 1.6
  led-row:
    fontFamily: "'Doto', 'Space Mono', monospace"
    fontSize: "1.28rem"
    fontWeight: 700
    letterSpacing: "0.03em"
    fontFeature: "\"tnum\""
  led-id:
    fontFamily: "'Doto', 'Space Mono', monospace"
    fontSize: "1.05rem"
    fontWeight: 700
    letterSpacing: "0.06em"
rounded:
  flap: "2px"
  xs: "3px"
  sm: "5px"
  md: "6px"
  lg: "8px"
  xl: "10px"
spacing:
  chip-gap: "0.45rem"
  board-inset: "1.1rem"
  column-gap: "1.2rem"
  block-gap: "2rem"
  hero-gap: "3rem"
  section: "clamp(4.5rem, 10vw, 7.5rem)"
  page-max: "78rem"
components:
  button-primary:
    backgroundColor: "{colors.cream}"
    textColor: "{colors.led-cell}"
    rounded: "{rounded.md}"
    padding: "0 1.2rem"
    height: "3.1rem"
  search-input:
    backgroundColor: "{colors.led-cell}"
    textColor: "{colors.cream}"
    rounded: "{rounded.md}"
    padding: "0 1rem 0 2.9rem"
    height: "3.1rem"
  key:
    backgroundColor: "{colors.cell-line}"
    textColor: "{colors.cream-muted}"
    typography: "{typography.label}"
    rounded: "{rounded.sm}"
    padding: "0 0.95rem"
    height: "2.5rem"
  key-selected:
    textColor: "{colors.cream}"
  nav-github:
    textColor: "{colors.cream}"
    typography: "{typography.label}"
    padding: "0.55rem 0.8rem"
  pill-queryable:
    backgroundColor: "{colors.teal-tint}"
    textColor: "{colors.queryable-teal}"
    rounded: "{rounded.xs}"
    padding: "0.35rem 0.5rem"
  pill-catalogued:
    textColor: "{colors.cream-muted}"
    rounded: "{rounded.xs}"
    padding: "0.35rem 0.5rem"
  board-row:
    backgroundColor: "{colors.led-cell}"
    textColor: "{colors.signal-amber}"
    typography: "{typography.led-row}"
    padding: "0.42rem 1.1rem"
  status-ok:
    textColor: "{colors.queryable-teal}"
    rounded: "{rounded.flap}"
  status-lead:
    backgroundColor: "{colors.lead-amber-hot}"
    textColor: "{colors.led-cell}"
    rounded: "{rounded.flap}"
  lead-ticket-header:
    backgroundColor: "{colors.signal-amber}"
    textColor: "{colors.led-cell}"
    padding: "0.9rem 1.1rem"
  domain-line-active:
    backgroundColor: "{colors.amber-tint}"
    textColor: "{colors.cream}"
    rounded: "{rounded.sm}"
    padding: "0.55rem 0.7rem"
  command-row:
    backgroundColor: "{colors.led-cell}"
    textColor: "{colors.cream}"
    typography: "{typography.code}"
    rounded: "{rounded.lg}"
    padding: "0.55rem 0.6rem 0.55rem 1.1rem"
---

# Design System: Anomaly

## Overview

**Creative North Star: "The Departures Board for Data"**

Anomaly is set as a station departures board. The page is the board's charcoal housing, ruled by the Buried Signals 40px amber grid; live data sits in amber LED dot-matrix on near-black cells with faint unlit dots; prose is cream Space Grotesk set straight on the housing, and every label, column head and command is Space Mono. Records arrive as rows, the board computes, and a row that doesn't fit flips its status characters to LEAD. That flip is the only moment the system spends solid amber.

The world is dense and operational rather than decorative: tables, rails, column heads, a route strip with stops, an interchange map, a printed ticket. Each component is a piece of transit or terminal hardware, and the data inside it is always real (generated catalogue, a computed z-score, a real runner output). Motion is mechanical: split-flap character flips, rows wiping in from the top, dashes travelling along map lines. All of it stops under reduced motion.

**Key Characteristics:**
- Charcoal housing with a 40px amber grid at 2.8% opacity behind everything.
- Doto LED dot-matrix in amber for board data, IDs and the domain hub; never for prose.
- Cream Space Grotesk for headlines and prose; Space Mono uppercase for labels.
- Steel teal marks what is queryable (and OK); amber marks detectors and leads.
- Solid amber fill appears only where a LEAD is declared.
- Thin cream rules divide rows; housings and cells carry 1px dark edges.

## Colors

A near-monochrome charcoal-and-cream terminal with two signal colours: amber for detection, steel teal for queryable data.

### Primary
- **Signal Amber** (signal-amber): the LED phosphor. Board rows, the clock, LED IDs in the catalogue, detector lines and the domain hub stroke on the interchange map, the headline's emphasised phrase, focus rings, the search caret and icon. As a solid fill, only on the lead ticket header.
- **Lead Amber Hot** (lead-amber-hot): the lit split-flap module. Fills each character cell of a LEAD status; also the text of the "Paid" pill.
- **Amber Tint / Amber Edge** (amber-tint, amber-edge): the selected state. Active domain line, input focus halo, hover borders on GitHub and copy buttons.

### Secondary
- **Queryable Teal** (queryable-teal): sources with an adapter, the OK status, JSON keys in the lead ticket, the copied state. A lightened steel teal chosen for legibility on near-black cells; the brand's base steel teal survives as the tint.
- **Teal Tint** (teal-tint): ground for the "Queryable" pill.

### Neutral
- **Housing Charcoal** (housing-charcoal): page background and title bar (at 92% with a 10px blur).
- **Board Housing** (board-housing): the hero board's casing and copy-button ground.
- **LED Cell** (led-cell): the near-black inside every display: board rows, catalogue board, map frame, ticket, command rows, inputs. Also the text colour on cream and amber fills.
- **Cell Head** (cell-head): column-head band and opened detail drawer in the catalogue.
- **Cell Line / Housing Edge / Field Edge** (cell-line, housing-edge, field-edge): dividers inside cells, 1px casing edges, and input/key borders respectively.
- **Cream** (cream): headlines, emphasised prose, the primary button fill, the current route stop.
- **Cream Muted / Cream Faint** (cream-muted, cream-faint): body prose and secondary labels; column heads, notes and placeholders.
- **Cream Rule** (cream-rule): row and list dividers on the housing.

### Named Rules
**The Lead Flip Rule.** Solid amber is a declaration. It fills only a LEAD: the split-flap status modules of a flagged row and the header of a lead ticket. Selection, activity and progress use amber tint, amber strokes or cream, never an amber fill.

**The Two Signals Rule.** Teal means a source an agent can query (and a record that passed). Amber means a detector or a lead. Catalogued-only sources fall back to faint cream. Don't swap them for decoration.

## Typography

**Display Font:** Space Grotesk (with system-ui)
**Label/Mono Font:** Space Mono (with ui-monospace)
**LED Font:** Doto (with Space Mono), weights 500/700/900 loaded, 700 in use

**Character:** Space Grotesk is the station signage, tight and confident at large sizes; Space Mono is the stencilled hardware labelling; Doto is the light-emitting display. Three voices, never mixed within one element.

### Hierarchy
- **Display** (600, clamp 2.9–5.6rem, 0.95, -0.035em): the hero headline only; 2.6rem on mobile. Balanced wrap.
- **Headline** (600, clamp 2–3.3rem, 1.02, -0.03em): section headings, max 22ch, written as plain sentences.
- **Title** (600, 1.22rem, -0.01em): route stop names; the promise list uses 1.08rem.
- **Lede** (400, 1.12rem, 1.55): the hero paragraph, 46ch; section intros run 1.08rem at 62ch in cream muted.
- **Body** (400, 1rem, 1.6): default prose.
- **Label** (Space Mono 400, 0.78rem, 0.12–0.14em, uppercase): nav, board head, command names, footer links.
- **Column label** (Space Mono 400, 0.66rem, 0.16em, uppercase): table column heads on the board and catalogue.
- **Code** (Space Mono 400, 0.88–0.9rem): commands, inline code, the ticket JSON (0.84rem).
- **LED row** (Doto 700, 1.28rem, 0.03em, tabular numbers, amber with an 8px amber glow): hero board data; 1rem on mobile. **LED ID** (Doto 700, 1.05rem): catalogue IDs, the clock, empty-state and hub labels.

### Named Rules
**The Lit Data Rule.** Doto is for data the board displays (records, IDs, the clock, a domain hub, the LEAD word). Prose, headings and controls never set in Doto.

## Layout

A single centred column, `min(100% - 2.5rem, 78rem)`, on the gridded housing. The hero pairs the headline and lede in a 1.25fr / 1fr grid aligned to the baseline, with the full-width board below; the catalogue search sits in the board's footer rail beside the primary button. Sections open with a fluid top pad (section token) and a headline plus intro, then a single component at 2.4–3.2rem below.

Tables are CSS grids with fixed data columns and one flexible column (board: 6.5 / 6.2 / flex / 7.5 / 4.5 / 7.4rem; catalogue: 18rem / flex / 9 / 7 / 8.5rem), padded by the 1.1rem board inset. The route strip is six equal columns on a 4px track.

Responsive: at 980px the route becomes three columns and loses its track, the interchange and lead sections stack, the domain list wraps as a row. At 760px the board drops TIME and RECORD columns and shows four rows, names wrap to their own line, the interchange SVG is replaced by a stacked list with the same teal/cream/amber node rings, catalogue rows collapse to ID + status with the title beneath, and secondary nav links hide (GitHub stays).

## Elevation & Depth

Depth is mostly tonal: charcoal housing, a slightly lighter board casing, near-black display cells inside, separated by 1px dark edges. The one lifted object is the hero board. Light is emitted, not cast: amber and teal LED text carry a soft text glow, and a 5px dot screen of unlit amber dots sits behind the board rows (4px behind catalogue IDs).

### Shadow Vocabulary
- **Board lift** (`box-shadow: 0 30px 60px -30px rgba(0,0,0,0.8), 0 0 0 1px rgba(0,0,0,0.4) inset`): the hero board only.
- **LED glow** (`text-shadow: 0 0 8px rgba(212,168,83,0.35)`; teal `0 0 6px rgba(125,177,174,0.35)`): lit data on cells.
- **Focus halo** (`box-shadow: 0 0 0 3px rgba(212,168,83,0.15)`): focused inputs.

### Named Rules
**The Emitted Light Rule.** Displays glow; housings don't cast. Add glow to lit data, not shadows to cards.

## Shapes

Small, hardware-like radii scaled by object size: 2px flap modules, 3px pills/tags/inline code, 5px keys and list buttons, 6px input and button, 8px command rows, 10px board-scale displays (hero board, catalogue board, map frame, ticket). Circles only for route stops and map nodes. Split-flap modules carry a 1px dark hinge line across their middle. The ticket's foot is divided by a dashed rule, like a tear line.

## Components

### Buttons
- **Shape:** gently rounded (md, 6px), 3.1rem tall to match the search field.
- **Primary:** solid cream with charcoal text, Space Grotesk 600 at 0.95rem, trailing arrow. One per view.
- **Hover / Active:** fill brightens to white; presses down 1px.
- **Icon (copy):** 2.4rem square on board housing with a field-edge border; amber on hover, teal when copied.

### Keys (tabs and filters)
- **Style:** physical keys on cell-line ground with a field-edge border, Space Mono uppercase labels, 2.5rem tall.
- **Selected:** cream 10% ground, cream border and text. Press nudges down 1px.

### Pills
- **Queryable:** teal on teal tint. **Catalogued:** muted cream on 7% cream. **Free:** teal text; **Needs key:** amber text; **Paid:** hot amber on amber tint.

### Cards / Containers (display cells)
- **Corner Style:** xl (10px) for display-scale cells, lg (8px) for command rows.
- **Background:** LED cell, with cell-head bands for column heads and open drawers.
- **Border:** 1px housing edge. Rows inside divide with cell-line or cream-rule.
- **Internal Padding:** board inset (1.1rem).

### Inputs / Fields
- **Style:** LED cell ground, field-edge border, 6px radius, amber search icon, amber caret.
- **Focus:** border turns amber with a 3px amber-tint halo.

### Navigation
- **Style:** sticky charcoal title bar at 92% with blur and a cream-rule bottom edge. Wordmark in Space Grotesk 600 with a dot-matrix glyph; links in Space Mono uppercase cream-muted, cream on hover. GitHub is an outlined 4px-radius chip that turns amber on hover. Mobile keeps only GitHub.

### Departures Board (signature)
Housing casing with a board head (live dot, Space Mono label, Doto amber clock), a column-label row, LED data rows, and a footer rail holding search and the primary button. A new row wipes in from the top (0.55s); its status flips character by character (0.09s per flap, linear) to OK in teal or LEAD in hot-amber modules, and a lead row gains an amber gradient wash from the left. Rows are scored for real; nothing blinks without a computation behind it.

### Route Strip (signature)
Six numbered stops on a 4px track; the track fills in cream to the current stop, past stops keep a 45% cream ring, the current stop is a solid cream disc with a soft cream halo. A command cell below shows the current stop's exchange in mono with an amber speaker tag.

### Interchange Map (signature)
Sources on the left (teal rings and dashed teal lines if queryable, faint cream if catalogued), a domain hub in the centre (amber 2px stroke, Doto amber name, mono table list), detectors on the right (amber rings and lines). Dashes travel along the lines.

### Lead Ticket (signature)
A display cell with a solid amber header (Doto "Lead" plus detector id), mono JSON body with teal keys, cream values and amber hashes, and a dashed-rule foot carrying provenance.

## Do's and Don'ts

### Do:
- **Do** keep solid amber for a LEAD declaration (flap modules, lead ticket header) and use amber tint or strokes everywhere else.
- **Do** set board data, IDs and clocks in Doto amber on LED cells with the dot screen behind them.
- **Do** mark queryable sources in teal and catalogued ones in faint cream, consistently across pills, map nodes and lists.
- **Do** keep the 40px amber grid (2.8%) on the housing behind every surface.
- **Do** drive every number, count and row from generated data or a real computation.
- **Do** honour reduced motion by stopping flips, wipes, flows and the live pulse.

### Don't:
- **Don't** fill buttons, selected states, badges or progress with solid amber; the primary button is cream and the current route stop is cream.
- **Don't** set prose, headings or controls in Doto.
- **Don't** add drop shadows to cells and cards; only the hero board is lifted.
- **Don't** animate the board without a computation behind it (no decorative blinking).
