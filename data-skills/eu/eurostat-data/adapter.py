"""Adapter for Eurostat's public SDMX 3.0 dissemination API."""

from __future__ import annotations

import heapq
import math
import re
import xml.etree.ElementTree as ET
from typing import Any
from urllib.parse import quote

import httpx

SOURCE_ID = "eu/eurostat/data"
SDMX_BASE = "https://ec.europa.eu/eurostat/api/dissemination/sdmx/3.0"
COMEXT_SDMX_BASE = "https://ec.europa.eu/eurostat/api/comext/dissemination/sdmx/3.0"
DATA_BROWSER = "https://ec.europa.eu/eurostat/databrowser/view"

_DATASET_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,127}$")
_VERSION_RE = re.compile(r"^(?:\d+(?:\.\d+)*|[~*])$")
_KEY_RE = re.compile(r"^[A-Za-z0-9_*+,-]+(?:\.[A-Za-z0-9_*+,-]+)*$")
_DIMENSION_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
_LANGUAGES = {"en", "de", "fr"}
_COMMON_INPUTS = {"mode", "language", "limit"}
_MODE_INPUTS = {
    "datasets": _COMMON_INPUTS | {"q", "offset"},
    "data": _COMMON_INPUTS
    | {
        "dataset_code",
        "version",
        "key",
        "filters",
        "first_n_observations",
        "last_n_observations",
        "allow_full_dataset",
    },
}
_XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"


class EurostatResponseError(httpx.HTTPError):
    """The upstream returned a successful response with an unusable contract."""


def _mode(input: dict[str, Any]) -> str:
    mode = input.get("mode")
    if mode is None:
        if input.get("dataset_code"):
            return "data"
        if input.get("q"):
            return "datasets"
        raise ValueError("Provide `q` to find datasets or `dataset_code` to query data.")
    if mode not in {"datasets", "data"}:
        raise ValueError("Unknown Eurostat mode; use `datasets` or `data`.")
    return mode


def _reject_unknown_inputs(input: dict[str, Any], mode: str) -> None:
    unknown = sorted(set(input) - _MODE_INPUTS[mode])
    if unknown:
        raise ValueError(
            f"Unsupported Eurostat {mode}-mode input(s): {', '.join(unknown)}."
        )


def _integer(
    input: dict[str, Any],
    name: str,
    default: int,
    *,
    minimum: int,
    maximum: int | None = None,
) -> int:
    value = input.get(name, default)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"`{name}` must be an integer.")
    if value < minimum or (maximum is not None and value > maximum):
        bound = f"{minimum}–{maximum}" if maximum is not None else f">= {minimum}"
        raise ValueError(f"`{name}` must be {bound}.")
    return value


def _language(input: dict[str, Any]) -> str:
    value = input.get("language", "en")
    if not isinstance(value, str) or value.lower() not in _LANGUAGES:
        raise ValueError("`language` must be `en`, `de`, or `fr`.")
    return value.lower()


def _scalar(value: Any, *, field: str) -> str:
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise ValueError(f"`{field}` values must be strings or numbers.")
    rendered = str(value).strip()
    if not rendered or any(ord(char) < 32 for char in rendered):
        raise ValueError(f"`{field}` values must be non-empty and contain no controls.")
    return rendered


def _component_filters(input: dict[str, Any]) -> dict[str, str]:
    raw = input.get("filters") or {}
    if not isinstance(raw, dict):
        raise ValueError("`filters` must be an object keyed by SDMX dimension ID.")
    filters: dict[str, str] = {}
    for dimension, value in raw.items():
        if not isinstance(dimension, str) or not _DIMENSION_RE.fullmatch(dimension):
            raise ValueError(f"Unsafe Eurostat dimension ID `{dimension}`.")
        if isinstance(value, list):
            if not value:
                raise ValueError(f"`filters.{dimension}` must not be an empty array.")
            rendered = ",".join(
                _scalar(item, field=f"filters.{dimension}") for item in value
            )
        else:
            rendered = _scalar(value, field=f"filters.{dimension}")
        filters[dimension.upper()] = rendered
    return filters


def _dataset_code(input: dict[str, Any]) -> str:
    value = input.get("dataset_code")
    if not isinstance(value, str) or not _DATASET_RE.fullmatch(value):
        raise ValueError(
            "`dataset_code` must be a Eurostat code containing letters, digits, "
            "underscores, or hyphens."
        )
    return value.upper()


def _version(input: dict[str, Any]) -> str:
    value = input.get("version", "1.0")
    if not isinstance(value, str) or not _VERSION_RE.fullmatch(value):
        raise ValueError("`version` must be an SDMX version such as `1.0`.")
    return value


def _series_key(input: dict[str, Any]) -> str | None:
    value = input.get("key")
    if value is None:
        return None
    if not isinstance(value, str) or not _KEY_RE.fullmatch(value):
        raise ValueError("`key` contains unsupported SDMX series-key characters.")
    return value


def _is_scoped_key(series_key: str | None) -> bool:
    """Return whether a series key constrains at least one component."""
    if series_key is None:
        return False
    return any(component.strip("*") for component in series_key.split("."))


def _observation_window(input: dict[str, Any], params: dict[str, Any]) -> None:
    first = input.get("first_n_observations")
    last = input.get("last_n_observations")
    if first is not None and last is not None:
        raise ValueError(
            "Use only one of `first_n_observations` or `last_n_observations`."
        )
    if first is not None:
        params["firstNObservations"] = _integer(
            input, "first_n_observations", 1, minimum=1, maximum=1000
        )
    if last is not None:
        params["lastNObservations"] = _integer(
            input, "last_n_observations", 1, minimum=1, maximum=1000
        )


def _source_url(dataset_code: str, language: str) -> str:
    return (
        f"{DATA_BROWSER}/{quote(dataset_code, safe='-_')}/default/table"
        f"?lang={language}"
    )


def _local_name(element: ET.Element) -> str:
    return element.tag.rsplit("}", 1)[-1]


def _children_text(element: ET.Element, child_name: str) -> list[tuple[str, str]]:
    values = []
    for child in element.iter():
        if _local_name(child) != child_name or not child.text:
            continue
        values.append((child.attrib.get(_XML_LANG, ""), child.text.strip()))
    return values


def _annotations(dataflow: ET.Element) -> dict[str, dict[str, str]]:
    annotations: dict[str, dict[str, str]] = {}
    for annotation in dataflow.iter():
        if _local_name(annotation) != "Annotation":
            continue
        fields: dict[str, str] = {}
        annotation_type = None
        for child in annotation:
            local = _local_name(child)
            if child.text and local in {
                "AnnotationType",
                "AnnotationTitle",
                "AnnotationURL",
                "AnnotationText",
            }:
                fields[local] = child.text.strip()
            if local == "AnnotationType" and child.text:
                annotation_type = child.text.strip()
        if annotation_type:
            annotations[annotation_type] = fields
    return annotations


def _annotation_value(
    annotations: dict[str, dict[str, str]], annotation_type: str, field: str
) -> str | None:
    return annotations.get(annotation_type, {}).get(field)


def _optional_int(value: str | None) -> int | None:
    try:
        return int(value) if value is not None else None
    except ValueError:
        return None


def _dataset_search(
    input: dict[str, Any], client: httpx.Client, language: str, limit: int
) -> dict[str, Any]:
    query = input.get("q")
    if not isinstance(query, str) or not query.strip():
        raise ValueError("`q` is required and must be non-empty in datasets mode.")
    offset = _integer(input, "offset", 0, minimum=0)
    url = f"{SDMX_BASE}/structure/dataflow/ESTAT/*/1.0"
    response = client.get(
        url,
        # allstubs includes codes and multilingual names while keeping the
        # all-dataflows response small enough for an interactive search.
        params={"detail": "allstubs", "compress": "false"},
        headers={"Accept": "application/vnd.sdmx.structure+xml;version=3.0.0"},
    )
    response.raise_for_status()
    try:
        root = ET.fromstring(response.text)
    except (ET.ParseError, TypeError) as exc:
        raise EurostatResponseError("Eurostat returned invalid SDMX structure XML.") from exc
    if _local_name(root) == "Fault":
        detail = next(
            (node.text for node in root.iter() if _local_name(node) == "faultstring"),
            "unknown SDMX fault",
        )
        raise EurostatResponseError(f"Eurostat dataflow query failed: {detail}")

    needle = query.strip().casefold()
    matches = []
    for dataflow in root.iter():
        if _local_name(dataflow) != "Dataflow":
            continue
        code = dataflow.attrib.get("id")
        if not code:
            continue
        names = dict(_children_text(dataflow, "Name"))
        descriptions = dict(_children_text(dataflow, "Description"))
        haystack = " ".join([code, *names.values(), *descriptions.values()]).casefold()
        if needle not in haystack:
            continue
        annotations = _annotations(dataflow)
        label = names.get(language) or names.get("en") or next(
            iter(names.values()), code
        )
        description = descriptions.get(language) or descriptions.get("en") or next(
            iter(descriptions.values()), None
        )
        matches.append(
            {
                "record_type": "dataset",
                "dataset_code": code,
                "dataset_label": label,
                "description": description,
                "version": dataflow.attrib.get("version") or "1.0",
                "updated": _annotation_value(
                    annotations, "DISSEMINATION_TIMESTAMP_DATA", "AnnotationTitle"
                )
                or _annotation_value(annotations, "UPDATE_DATA", "AnnotationTitle"),
                "observation_count": _optional_int(
                    _annotation_value(annotations, "OBS_COUNT", "AnnotationTitle")
                ),
                "oldest_period": _annotation_value(
                    annotations, "OBS_PERIOD_OVERALL_OLDEST", "AnnotationTitle"
                ),
                "latest_period": _annotation_value(
                    annotations, "OBS_PERIOD_OVERALL_LATEST", "AnnotationTitle"
                ),
                "metadata_url": _annotation_value(
                    annotations, "ESMS_HTML", "AnnotationURL"
                ),
                "source_url": _source_url(code, language),
            }
        )
    matches.sort(key=lambda record: record["dataset_code"])
    records = matches[offset : offset + limit]
    return {
        "source_id": SOURCE_ID,
        "mode": "datasets",
        "records": records,
        "page": {
            "query": query.strip(),
            "limit": limit,
            "offset": offset,
            "returned": len(records),
            "total": len(matches),
        },
    }


def _indexed_value(container: Any, index: int) -> Any:
    if isinstance(container, dict):
        return container.get(str(index), container.get(index))
    if isinstance(container, list) and index < len(container):
        return container[index]
    return None


def _positions(container: Any, *, total_cells: int, field: str) -> set[int]:
    if container is None:
        return set()
    if isinstance(container, dict):
        raw_positions = container.keys()
    elif isinstance(container, list):
        raw_positions = range(len(container))
    else:
        raise EurostatResponseError(f"Eurostat JSON-stat `{field}` is not an object or array.")
    positions = set()
    for raw_position in raw_positions:
        try:
            position = int(raw_position)
        except (TypeError, ValueError) as exc:
            raise EurostatResponseError(
                f"Eurostat JSON-stat `{field}` has a non-numeric position."
            ) from exc
        value = _indexed_value(container, position)
        if value is None:
            continue
        if position < 0 or position >= total_cells:
            raise EurostatResponseError(
                f"Eurostat JSON-stat `{field}` position is outside the cube."
            )
        positions.add(position)
    return positions


def _category_codes(
    dimension_id: str, dimension: dict[str, Any], expected_size: int
) -> tuple[list[str], dict[str, Any]]:
    category = dimension.get("category")
    if not isinstance(category, dict):
        raise EurostatResponseError(
            f"Eurostat JSON-stat dimension `{dimension_id}` has no category object."
        )
    index = category.get("index")
    if isinstance(index, list):
        codes = [str(code) for code in index]
    elif isinstance(index, dict):
        codes_by_position: list[str | None] = [None] * expected_size
        for code, raw_position in index.items():
            if isinstance(raw_position, bool) or not isinstance(raw_position, int):
                raise EurostatResponseError(
                    f"Eurostat dimension `{dimension_id}` has an invalid category index."
                )
            if raw_position < 0 or raw_position >= expected_size:
                raise EurostatResponseError(
                    f"Eurostat dimension `{dimension_id}` category is outside its size."
                )
            codes_by_position[raw_position] = str(code)
        if any(code is None for code in codes_by_position):
            raise EurostatResponseError(
                f"Eurostat dimension `{dimension_id}` category index is incomplete."
            )
        codes = [code for code in codes_by_position if code is not None]
    else:
        raise EurostatResponseError(
            f"Eurostat dimension `{dimension_id}` has no usable category index."
        )
    if len(codes) != expected_size:
        raise EurostatResponseError(
            f"Eurostat dimension `{dimension_id}` size does not match its categories."
        )
    labels = category.get("label")
    return codes, labels if isinstance(labels, dict) else {}


def _coordinates(flat_position: int, sizes: list[int]) -> list[int]:
    coordinates = [0] * len(sizes)
    remainder = flat_position
    for position in range(len(sizes) - 1, -1, -1):
        coordinates[position] = remainder % sizes[position]
        remainder //= sizes[position]
    if remainder:
        raise EurostatResponseError("Eurostat JSON-stat position exceeds cube dimensions.")
    return coordinates


def _status_labels(payload: dict[str, Any]) -> dict[str, Any]:
    extension = payload.get("extension")
    if not isinstance(extension, dict):
        return {}
    status_meta = extension.get("status")
    if not isinstance(status_meta, dict):
        return {}
    labels = status_meta.get("label")
    return labels if isinstance(labels, dict) else {}


def _flatten_cube(
    payload: dict[str, Any],
    *,
    dataset_code: str,
    language: str,
    limit: int,
) -> tuple[list[dict[str, Any]], int]:
    if payload.get("class") != "dataset":
        raise EurostatResponseError("Eurostat did not return a JSON-stat dataset.")
    dimension_ids = payload.get("id")
    sizes = payload.get("size")
    dimensions = payload.get("dimension")
    if (
        not isinstance(dimension_ids, list)
        or not isinstance(sizes, list)
        or len(dimension_ids) != len(sizes)
        or not isinstance(dimensions, dict)
        or any(
            isinstance(size, bool) or not isinstance(size, int) or size < 0
            for size in sizes
        )
    ):
        raise EurostatResponseError("Eurostat returned malformed JSON-stat dimensions.")
    total_cells = math.prod(sizes)
    value_positions = _positions(
        payload.get("value"), total_cells=total_cells, field="value"
    )
    status_positions = _positions(
        payload.get("status"), total_cells=total_cells, field="status"
    )
    positions = value_positions | status_positions

    category_codes: dict[str, list[str]] = {}
    category_labels: dict[str, dict[str, Any]] = {}
    for dimension_id, size in zip(dimension_ids, sizes, strict=True):
        dimension = dimensions.get(dimension_id)
        if not isinstance(dimension_id, str) or not isinstance(dimension, dict):
            raise EurostatResponseError(
                "Eurostat JSON-stat dimension metadata is incomplete."
            )
        codes, labels = _category_codes(dimension_id, dimension, size)
        category_codes[dimension_id] = codes
        category_labels[dimension_id] = labels

    status_labels = _status_labels(payload)
    time_dimension = next(
        (
            dimension_id
            for dimension_id in dimension_ids
            if dimension_id.casefold() in {"time", "time_period"}
        ),
        None,
    )
    unit_dimension = next(
        (
            dimension_id
            for dimension_id in dimension_ids
            if dimension_id.casefold() == "unit"
        ),
        None,
    )
    dataset_label = payload.get("label")
    updated = payload.get("updated")
    source_url = _source_url(dataset_code, language)

    records = []
    for flat_position in heapq.nsmallest(limit, positions):
        coordinates = _coordinates(flat_position, sizes)
        codes = {
            dimension_id: category_codes[dimension_id][coordinate]
            for dimension_id, coordinate in zip(
                dimension_ids, coordinates, strict=True
            )
        }
        labels = {
            dimension_id: category_labels[dimension_id].get(code, code)
            for dimension_id, code in codes.items()
        }
        status = _indexed_value(payload.get("status"), flat_position)
        records.append(
            {
                "record_type": "observation",
                "dataset_code": dataset_code,
                "dataset_label": dataset_label,
                "updated": updated,
                "time_period": codes.get(time_dimension) if time_dimension else None,
                "value": _indexed_value(payload.get("value"), flat_position),
                "unit": codes.get(unit_dimension) if unit_dimension else None,
                "status": status,
                "status_label": status_labels.get(str(status)),
                "dimensions": codes,
                "dimension_labels": labels,
                "source_url": source_url,
            }
        )
    return records, len(positions)


def _data_query(
    input: dict[str, Any], client: httpx.Client, language: str, limit: int
) -> dict[str, Any]:
    dataset_code = _dataset_code(input)
    version = _version(input)
    series_key = _series_key(input)
    filters = _component_filters(input)
    allow_full = input.get("allow_full_dataset", False)
    if not isinstance(allow_full, bool):
        raise ValueError("`allow_full_dataset` must be a boolean.")
    scoped_key = _is_scoped_key(series_key)
    if not filters and not scoped_key and not allow_full:
        raise ValueError(
            "Provide `filters` or a non-wildcard `key`; a local `limit` does "
            "not make an unfiltered Eurostat download safe. Set "
            "`allow_full_dataset:true` only for a known-small dataset."
        )
    if dataset_code.startswith("DS-") and not filters and not scoped_key:
        raise ValueError("`DS-` Comext/Prodcom datasets always require filters.")

    base = COMEXT_SDMX_BASE if dataset_code.startswith("DS-") else SDMX_BASE
    url = (
        f"{base}/data/dataflow/ESTAT/{quote(dataset_code, safe='-_')}/"
        f"{quote(version, safe='.*~')}"
    )
    if series_key:
        url += f"/{quote(series_key, safe='.*,+-_')}"
    # Eurostat otherwise returns gzip bytes without a Content-Encoding header,
    # which prevents standard HTTP clients from decoding the advertised JSON.
    params: dict[str, Any] = {
        "format": "json",
        "lang": language.upper(),
        "compress": "false",
    }
    params.update({f"c[{dimension}]": value for dimension, value in filters.items()})
    _observation_window(input, params)

    response = client.get(url, params=params)
    if response.status_code == 202:
        raise EurostatResponseError(
            "Eurostat made this extraction asynchronous; add narrower filters."
        )
    response.raise_for_status()
    try:
        payload = response.json()
    except (TypeError, ValueError) as exc:
        raise EurostatResponseError(
            "Eurostat returned a non-JSON response; the query may be too broad."
        ) from exc
    if not isinstance(payload, dict):
        raise EurostatResponseError("Eurostat returned an unexpected JSON response.")
    records, total = _flatten_cube(
        payload, dataset_code=dataset_code, language=language, limit=limit
    )
    return {
        "source_id": SOURCE_ID,
        "mode": "data",
        "records": records,
        "page": {
            "dataset_code": dataset_code,
            "limit": limit,
            "returned": len(records),
            "total_observations": total,
            "truncated": total > limit,
            "updated": payload.get("updated"),
        },
    }


def run(input: dict, ctx) -> dict:
    if not isinstance(input, dict):
        raise ValueError("Eurostat input must be an object.")
    mode = _mode(input)
    _reject_unknown_inputs(input, mode)
    language = _language(input)
    limit = _integer(input, "limit", 100, minimum=1, maximum=1000)
    with httpx.Client(
        headers={"User-Agent": "BuriedSignals-Navigator/1.0"}, timeout=60
    ) as client:
        if mode == "datasets":
            return _dataset_search(input, client, language, limit)
        return _data_query(input, client, language, limit)
