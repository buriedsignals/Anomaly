# Anomaly homepage plan

## Direction

Describe the product through the work it does for a journalist. Keep the
homepage focused on three features:

1. a scalable registry of anomaly detectors;
2. a catalogue of skills for acquiring public data;
3. traceable proposed findings, review, and report generation.

The complete P0–P7 sequence stays in `docs/flow.html`.

## Homepage

### Hero

**Headline**

> An agent workflow for finding anomalies in structured data.

**Description**

> Turn your agent into a structured-data investigation system.

**Explanation**

> A portable skill that acquires or registers data, profiles it with Python and DuckDB, recommends relevant anomaly detectors, runs the tests you approve, and checks proposed findings through replay and independent review.

Actions: `View on GitHub →` and `Read the full workflow →`.

### Problem

**Heading**

> One dataset can contain many kinds of anomalies.

Use concrete examples: unusual values, changes over time, repeated payments,
shared addresses, network clusters, and copied passages. Explain that each
pattern needs a compatible detector and visible assumptions.

### Anomaly detectors

**Heading**

> Run the right tests for the data in front of you.

**Copy**

> A detector is a reusable test for one pattern: duplicate payments, unusual timing, shared entities, geographic clusters, copied text, and more.

> Anomaly profiles the dataset, recommends up to ten compatible detectors, and shows why each was selected before you approve the run.

Show two continuously moving rows of real detector examples from the registry.
The animation is CSS-only, pauses on hover, and becomes a static wrapped list
when reduced motion is requested.

Supporting features:

- incompatible detectors are removed automatically;
- recommendations expose parameters, assumptions, and false positives;
- new detector packages join the registry without loading the full catalogue
  into the agent context.

### Public-data skills

**Heading**

> Bring public records into the same case.

**Copy**

> Choose a source skill and Anomaly handles the source-specific query, validation, normalization, and provenance.

> Add your own files alongside public data. Everything is profiled and tested through the same workflow.

Show representative checked-in sources: USAspending, SEC EDGAR, OpenFEC, TED,
Companies House, OpenCorporates, CourtListener, OpenSanctions, and Wikidata.

### Findings and report

**Heading**

> Every proposed finding points back to the data.

**Copy**

> Anomaly turns detector signals into draft claims with evidence references, source and detector hashes, recorded runs, previews, and calculations.

> Replay checks the math. A separate reviewer challenges the draft. You decide what becomes a finding.

Show the short path:

`Signal → Proposed finding → Replay and review → Journalist decision`

Explain the outputs:

- claims retain signal IDs, source and detector hashes, run IDs, evidence
  references, and replayable calculations;
- only approved claims enter `findings/findings.json`;
- Anomaly writes `findings/report.md`, `findings/unresolved.md`, and
  deterministic SVG charts from accepted findings.

### Final action

Delete the workflow-summary section.

**Heading**

> Run Anomaly on your data.

**Copy**

> Start a case with your own files or choose a source from the public-data catalogue.

Actions: `Open Anomaly on GitHub →` and `Read the full workflow →`.

## Full workflow page

`docs/flow.html` contains:

- P0–P7;
- Gate A and Gate B;
- the artifact chain from source records to accepted findings;
- the bounded remediation pass;
- links back to the homepage and repository.

## Product boundary

Anomaly currently has no semantic search over source data and no searchable
anomaly index. Detector metadata supports simple registry filtering, and case
signals/results are stored as structured JSONL, Parquet, and DuckDB artifacts,
but the homepage must not present those as a search feature.

## Build

- self-contained `index.html` and `docs/flow.html`;
- black text on white with neutral gray only;
- system sans-serif and monospace labels;
- no JavaScript, external fonts, assets, tracking, or gradients;
- semantic landmarks, visible focus, responsive layout, print styles, and
  reduced-motion handling.

The current repository URL is `https://github.com/tomvaillant/Anomaly` and is
private. Confirm the final public URL before launch.
