# Product

<!-- impeccable:product-schema 1 -->

Recorded 2026-10-27 from Tom's brief and the repository. Tom was unavailable and
delegated judgement; facts marked *(inferred)* were not confirmed by him.

## Platform

web

## Users

- Investigating agents and the journalists or researchers who run them, most
  often through Spotlight (Buried Signals' OSINT pipeline), on a frontier model
  or locally. The agent needs to know which data could help a case, how to get
  it, and which anomaly tests fit it.
- Developers and newsroom technologists evaluating Anomaly on GitHub before
  wiring it into their own agent *(inferred from the open-source repo and site)*.

## Product Purpose

Anomaly is context plus one runner. It tells an investigating agent which data
sources could help an investigation, how to get and use each one (access, key,
cost, licence), and which detectors fit that type of data. It then runs those
detectors deterministically on tables the agent fetched and returns leads with
provenance. Success: an agent goes from "is there data for this?" to replayable
leads without the model doing arithmetic.

## Positioning

Sources and detectors never reference each other; both point at a domain (a
type of data such as lobbying or procurement), with shared table contracts for
multi-table detectors. That lets hundreds of sources and many detector families
grow independently. Detection is SQL in a sealed DuckDB, so the same tables
always give the same result, and every output is a lead, never a finding.

## Operating Context

- Lookup: `python -m anomaly.context [--domain D | --source ID]` (JSON).
- Runner: `python -m anomaly.oneshot --table FILE` (core detectors, role
  mapping) or repeated `--tables NAME=PATH` (domain detectors).
- Spotlight pins `detectors/catalogue.json` by `catalogue_hash`; an opted-in
  investigation reads the lookup at Methodology, the investigator runs
  detectors during Investigation, and signals reach the Investigation gate as
  leads.
- A standalone case workflow (P0 to P7, two journalist gates, replay and an
  independent reviewer) exists for use without another agent.

## Capabilities and Constraints

- Counts change; the site reads them from the generated lookup, never from
  hand-typed numbers.
- Sources are `queryable` (adapter) or `catalogued` (documented only).
- Draft detectors are never offered and must not be presented as available.
- No hosted service, account, pricing or API: it is a local Python package.

## Brand Commitments

- A Buried Signals product: charcoal, cream, amber, steel teal; Space Grotesk
  and Space Mono; Detection motifs for tool pages (brand skill).
- Sibling of Spotlight (spotlight.buriedsignals.com), which has a numbered
  pipeline diagram; Tom asked for a comparable flow diagram here.
- Tom's voice rules (wiki `writing/VOICE.md`): plain sentences, numbers and
  mechanisms over adjectives, no hype.

## Evidence on Hand

- The live catalogue: `python -m anomaly.context` output (domains, sources,
  detectors) and `detectors/catalogue.json`.
- A real lead from a lobbying run (foreign filings fixture) for an example
  signal.
- No customers, testimonials, benchmarks or usage numbers exist; do not invent
  any.

## Product Principles

1. Leads, never findings: the product only ever claims to flag.
2. The catalogue is the truth: everything shown is generated from it.
3. Deterministic over clever: code computes, the model chooses.
4. Domains keep it scalable: no source is wired to a detector.
