# Detector catalogue and one-shot runs

For tools outside Anomaly that want to see which detectors exist and run one
on a small table without creating a case.

## Catalogue

`detectors/catalogue.json` is generated from every `detectors/**/meta.yaml`
whose `release` is `released`. `_template` and `release: draft` packages are
excluded.

```bash
python -m anomaly.catalogue            # print the catalogue
python -m anomaly.catalogue --write    # regenerate the checked-in file
python -m anomaly.catalogue --check    # exit 1 when the file is stale
```

`tests/test_catalogue.py` fails when the checked-in file is stale, so a
`meta.yaml` or `query.sql` change must ship with a regenerated catalogue.

### Schema (`schema_version: 1`)

| Key | Meaning |
|---|---|
| `schema_version` | Integer. Bumped on any breaking change to this schema. |
| `catalogue_hash` | `sha256:` over the canonical JSON of the other three keys. |
| `detectors` | Released entries, sorted by `id`. |
| `signal_schema` | Shape of each record `anomaly.oneshot` emits. |

Each detector entry:

| Key | Meaning |
|---|---|
| `id`, `version` | Package identity. |
| `implementation_hash` | `sha256:` over every file in the package; equals `detector_hash` on the signals it produces. |
| `family`, `group`, `signal_category`, `severity`, `title`, `description` | Classification and labels. |
| `data_type` | The domain a detector reads (e.g. `lobbying`); absent for core detectors that run on any table. Its tables are declared in `domains/<data_type>.yaml`. |
| `required_tables` | `["*"]` means any one table; named tables need a prepared case. |
| `required_fields` | `[{name, types}]`. `types` is the package's declared `required_types` for that field, or `null` when the package declares none. |
| `parameters` | `{name: {default, type, ...bounds}}`. `integer`/`number` carry `minimum`/`maximum` (inclusive); `string` carries `max_length`. |
| `expected_output`, `assumptions`, `false_positives` | As declared in `meta.yaml`. |
| `sensitive_output` | `redact`, `reference` or `none`. |
| `resource_limits` | Ceilings a caller may only tighten. |
| `attribution`, `source_repository` | Present for vendored packages. |

### Package fields that feed the catalogue

`meta.yaml` declares `release: released | draft` and a `parameter_bounds`
entry for every key in `parameters`. Building the catalogue refuses a released
package with a missing, incomplete or violated bound.

## One-shot runs

```bash
python -m anomaly.oneshot --table records.csv --request request.json --approved
```

`request.json` is one object or a list of at most ten:

```json
{
  "id": "numeric.zscore_outliers",
  "version": "1.1.0",
  "fields": {"id": "record_id", "amount": "value"},
  "parameters": {"z_threshold": 4.0}
}
```

`implementation_hash` may replace or accompany `version`; at least one is
required. Python callers use `anomaly.oneshot.run_detectors(table, requests,
approved=True)`.

The run refuses:

- a detector absent from the released catalogue, or whose `version` or
  `implementation_hash` differs from it;
- an installed package that no longer matches its catalogue entry;
- a detector that needs named case tables;
- unmapped required fields, mapped columns missing from the table, and unknown,
  wrongly typed or out-of-bounds parameters;
- more than ten detectors, duplicate detectors, or no `--approved`.

Only mapped columns are loaded, renamed to the detector's field names, into an
in-memory DuckDB that is then sealed with external access disabled. Detector
SQL passes the same read-only validation as case runs, and the detector's
declared resource limits cap the run. Output is JSONL in `signal_schema`; every
record has `status: "lead"` and its `values` follow `sensitive_output`.

Anomaly does not record the approval. The caller owns its approval gate and
case files; Anomaly's own Gates A and B are not involved.
