<div align="center">

# Anomaly

### Evidence-led data investigations for AI agents

**Turns a dataset into reviewed, traceable findings — deterministic detectors, replayed calculations, independent review, and two journalist gates. 28 public-data skills, 32 detectors, one portable case format.**

[Workflow](#investigation-workflow) | [Detectors](#detectors) | [Data Skills](#public-data-skills) | [Evidence Viewer](#evidence-viewer) | [Website](https://anomaly.buriedsignals.com/)

[![28 Data Skills](https://img.shields.io/badge/data_skills-28-0080ff?style=for-the-badge&logo=bookstack&logoColor=white)](#public-data-skills)[![32 Detectors](https://img.shields.io/badge/detectors-32-aa00ff?style=for-the-badge&logo=filter&logoColor=white)](#detectors)[![2 Gates](https://img.shields.io/badge/journalist_gates-2-00bfa5?style=for-the-badge&logo=verified&logoColor=white)](#investigation-workflow)[![Website](https://img.shields.io/badge/site-anomaly.buriedsignals.com-00c853?style=for-the-badge&logo=googlechrome&logoColor=white)](https://anomaly.buriedsignals.com/)

[![Stars](https://img.shields.io/github/stars/buriedsignals/Anomaly?style=flat-square&logo=github&label=Stars)](https://github.com/buriedsignals/Anomaly/stargazers)[![Issues](https://img.shields.io/github/issues/buriedsignals/Anomaly?style=flat-square&logo=github&label=Issues)](https://github.com/buriedsignals/Anomaly/issues)[![Last Commit](https://img.shields.io/github/last-commit/buriedsignals/Anomaly?style=flat-square&logo=github&label=Last%20Commit)](https://github.com/buriedsignals/Anomaly/commits)[![Contributors](https://img.shields.io/github/contributors/buriedsignals/Anomaly?style=flat-square&logo=github&label=Contributors)](https://github.com/buriedsignals/Anomaly/graphs/contributors)

Built by [**Buried Signals**](https://buriedsignals.com/) • [tom@buriedsignals.com](mailto:tom@buriedsignals.com)

</div>

---

Anomaly is an agent workflow for finding anomalies in structured data. It
acquires or registers data, profiles it with Python and DuckDB, recommends
compatible anomaly detectors, runs the tests the journalist approves, and
checks proposed findings through deterministic replay and independent review.

It is built for active structured-data investigations. Give it a CSV, a folder
of local files, or a public-data source; it builds a portable case folder,
profiles what is actually there, and records every unusual pattern as a lead —
never a conclusion. An unusual value, a repeated payment, a shared address, or
a copied passage becomes a structured signal with provenance, and only replay,
independent review, and journalist approval can turn a lead into a finding.

## What Anomaly Does

- Registers journalist-supplied files or acquires public records through
  source-specific data skills, with hashes, licensing, and provenance.
- Profiles tables, fields, types, missingness, distributions, duplicates, and
  coverage before any test runs.
- Recommends no more than ten compatible detectors, each with parameters,
  assumptions, selection reasons, and known false positives.
- Waits for Gate A: no detector executes until the journalist approves scope,
  mappings, and the detector plan.
- Runs approved detectors read-only in DuckDB with external access disabled,
  bounded memory, time, threads, and output.
- Drafts proposed findings from ranked, redacted signal previews with
  alternative explanations, limitations, and confidence.
- Replays every cited calculation against recorded source and detector hashes.
- Runs an independent, read-only data reviewer that challenges coverage,
  denominators, baselines, selection bias, and claim wording.
- Waits for Gate B: only claims the journalist accepts become findings.
- Writes the report, deterministic charts, and a self-contained evidence
  viewer into a portable case folder.

## Investigation Workflow

```text
P0 Create or resume case
  -> P1 Acquire or register data
  -> P2 Prepare, contextualize, and profile
  -> P3 Recommend <= 10 detectors
  -> GATE A journalist approves scope and detector plan
  -> P4 Run approved detectors
  -> P5 Draft proposed findings
  -> P6 Replay calculations + independent review
  -> GATE B journalist accepts, revises, or rejects
  -> P7 Findings, report, charts, evidence viewer
```

Both gates are explicit. Anomaly does not auto-advance through detector-plan
approval or the findings decision, and it never infers progress from report
files. One remediation pass may return from review to detector execution or
drafting; further cycles require journalist approval.

A detector identifies an observation. It does not establish identity, intent,
causation, fraud, or wrongdoing. Severity is triage priority, not proof.

## Case Outputs

Each investigation gets a portable case folder. All references are relative;
moving the folder changes nothing.

```text
{CASE}/
├── AGENTS.md                    # safety instructions for any agent
├── README.md                    # journalist entry point and status
├── case.json
├── instructions/                # methodology, context, data dictionary, handling
├── data/
│   ├── sources.json             # every input: hash, license, sensitivity
│   ├── raw/                     # included originals
│   ├── prepared/                # normalized tables + transformation notes
│   └── index.duckdb             # investigation database
├── detectors/
│   ├── plan.json                # recommended + approved plan
│   └── used/                    # content-addressed detector snapshots
├── evidence/
│   ├── signals.jsonl            # canonical leads
│   ├── replay.json              # replayed calculations
│   └── runs/                    # full outputs + provenance per run
├── findings/
│   ├── draft.json               # proposed claims (immutable)
│   ├── review.json              # replay status + independent verdicts
│   ├── findings.json            # only Gate-B-accepted claims
│   ├── unresolved.md
│   ├── report.md
│   ├── charts/                  # deterministic SVGs
│   └── viewer.html              # self-contained evidence viewer
└── .anomaly/                    # durable state, receipts, attempts
```

## Detectors

Detectors are executable packages in a generated registry, grouped by the kind
of data they inspect: **table, numeric, categorical, temporal, relational,
network, geospatial, text, cross-dataset, credential, and domain**. Anomaly
profiles the dataset first, removes incompatible packages, and loads only the
metadata relevant to the current dataset.

A detector package is one folder: `meta.yaml` (requirements, parameters,
assumptions, false positives, resource limits), one parameterized read-only
SQL query or trusted Python file, and positive/negative/boundary/false-positive
fixtures. SQL runs sandboxed in DuckDB; DDL, DML, `ATTACH`, `COPY`, and
external readers are rejected. Add your own by copying
[`detectors/_template/`](detectors/_template/) and running the validator.

## Public Data Skills

The `data-skills/` catalogue teaches Anomaly how to acquire public records:
each skill defines the source query, response validation, normalization, and
provenance/licensing capture. An adapter loads only when its source is
requested.

| Region | Sources |
|---|---|
| **United States** | USAspending awards · SEC EDGAR filings · OpenFEC campaign finance · Federal Register · EPA Envirofacts · CourtListener (search, dockets, opinions, judges, financial disclosures) · Congress legislation |
| **Europe** | EU TED procurement · Eurostat · European Parliament open data · Find-a-Tender |
| **United Kingdom** | Companies House companies · Find-a-Tender notices |
| **Global** | OpenSanctions · OpenCorporates · GLEIF LEI records · OCCRP Aleph · Wikidata · GDELT news · Bluesky posts |
| **National registries** | CH Zefix companies · FR Pappers companies · NO Brreg enheter · OpenParldata parliamentary data |

Journalist-supplied files enter the same workflow and receive the same
provenance, profiling, and replay treatment as acquired data.

## Evidence Viewer

Every completed case ships `findings/viewer.html`: a self-contained evidence
inspector with no external resources. Click any accepted claim to open its
full chain — supporting signals with detector identity and severity, evidence
references, replayed calculations, redacted previews, detector provenance —
plus the independent-review context and unresolved work. All case-controlled
text is redacted and rendered inert; the file can be shared like any other
case artifact.

## Install

Anomaly is a local Python package plus one installed skill and one reviewer
agent. Requirements: Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/buriedsignals/Anomaly.git
cd Anomaly
uv sync --extra test
uv run pytest tests/          # 811 tests, fully local
```

Point your agent runtime at [`skills/anomaly/SKILL.md`](skills/anomaly/SKILL.md)
(the operator contract) and
[`agents/anomaly-data-reviewer.md`](agents/anomaly-data-reviewer.md) (the
independent reviewer). The packaged demo in `tests/fixtures/` walks a complete
case from source registration through Gate B, report, charts, and viewer.

## Documentation

| Doc | For |
|---|---|
| [Website](https://anomaly.buriedsignals.com/) | Product overview. |
| [Workflow reference](https://anomaly.buriedsignals.com/docs/flow.html) | Every phase, both gates, artifacts, and remediation. |
| [`skills/anomaly/SKILL.md`](skills/anomaly/SKILL.md) | Operator contract: dispatch table, gates, retries, redaction. |
| [`agents/anomaly-data-reviewer.md`](agents/anomaly-data-reviewer.md) | Independent reviewer contract and verdict taxonomy. |
| [`AGENTS.md`](AGENTS.md) | Repository workflow and product constraints. |
| [`PRD`-lineage design notes](skills/anomaly/SKILL.md) | Case-folder and registry rationale. |

## What Belongs Where

- **Anomaly** is structured-data investigation: acquisition, profiling,
  detectors, replay, reviewed findings, and the portable case folder.
- **Spotlight** is active OSINT casework: leads, source captures, fact-checks,
  and review artifacts across public web sources.
- **Splash** is visual journalism: storyboards, rendered visuals, and
  delivery.
- Findings from Anomaly are hand-off artifacts — a reviewed findings file and
  evidence viewer a journalist can carry into any editorial workflow.

## Acknowledgements

Anomaly stands on open work — open-source projects, open data platforms, and
open methods. A sincere thank-you to every project below. *(Listing does not
imply affiliation or endorsement.)*

| Category | Projects we're grateful to |
|----------|----------------------------|
| **Computation** | [DuckDB](https://duckdb.org/) (MIT — the read-only investigation engine) · [Apache Arrow / PyArrow](https://arrow.apache.org/) (Apache-2.0) |
| **Public data platforms** | [USAspending](https://www.usaspending.gov/) · [SEC EDGAR](https://www.sec.gov/edgar) · [OpenFEC](https://api.open.fec.gov/) · [CourtListener / Free Law Project](https://www.courtlistener.com/) · [Federal Register](https://www.federalregister.gov/) · [US EPA Envirofacts](https://www.epa.gov/envirofacts) · [Congress.gov](https://www.congress.gov/) |
| **Companies & entities** | [Companies House](https://find-and-update.company-information.service.gov.uk/) · [OpenCorporates](https://opencorporates.com/) · [GLEIF](https://www.gleif.org/) · [OCCRP Aleph](https://aleph.occrp.org/) · [OpenSanctions](https://www.opensanctions.org/) · [Wikidata](https://www.wikidata.org/) · CH Zefix · Pappers · Brreg |
| **Procurement & parliament** | [EU TED](https://ted.europa.eu/) · [Eurostat](https://ec.europa.eu/eurostat) · [European Parliament open data](https://data.europarl.europa.eu/) · OpenParldata |
| **Methodology** | [Data2Story](https://github.com/QinghongLin/data2story-skill) by Qinghong Lin et al. (context-before-interpretation, stable evidence IDs, artifact-based handoffs) · [Spotlight](https://github.com/buriedsignals/spotlight) (gates, durable state, and bounded-retry discipline Anomaly inherited) |

> Built something here we should credit, or want a listing changed or removed?
> Open an issue or PR — we'll fix it fast.

## License

No LICENSE file has been published yet. All rights reserved by Buried Signals
pending an explicit license.
