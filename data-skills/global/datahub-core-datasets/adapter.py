"""Adapter for global/datahub/core-datasets — DataHub Core datasets (public).

DataHub's Core collection publishes curated reference datasets (GDP, country
codes, ...) as Frictionless data packages: a datapackage.json describing each
resource and its licence, plus CSV files under https://datahub.io/core/<name>/_r/-/.
No key. Two ops: read a package's metadata, and fetch a bounded number of rows
from one CSV resource. Licences vary per dataset and are copied from each
package's own `licenses` field onto every record.
"""

from __future__ import annotations

import csv
import re

import httpx

CORE_URL = "https://datahub.io/core"
SOURCE_ID = "global/datahub/core-datasets"
UA = "BuriedSignals-catalogue/1.0 (https://buriedsignals.com; catalogue@buriedsignals.com)"
_DATASET = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_RESOURCE_PATH = re.compile(r"^[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*$")


def _dataset(input: dict) -> str:
    dataset = input.get("dataset")
    if not isinstance(dataset, str) or not _DATASET.fullmatch(dataset.strip()):
        raise ValueError("dataset must be a DataHub Core dataset name such as 'gdp'.")
    return dataset.strip()


def _base(dataset: str) -> str:
    return f"{CORE_URL}/{dataset}/_r/-"


def _licenses(package: dict) -> list[dict]:
    return [
        {"name": item.get("name"), "path": item.get("path"), "title": item.get("title")}
        for item in package.get("licenses") or []
        if isinstance(item, dict)
    ]


def _license_label(licenses: list[dict]) -> str | None:
    names = [item["name"] or item["title"] for item in licenses if item["name"] or item["title"]]
    return "; ".join(names) or None


def _resource_url(dataset: str, resource: dict) -> str | None:
    """Resolve a relative resource path under the dataset; refuse anything else."""
    path = resource.get("path")
    if not isinstance(path, str) or not _RESOURCE_PATH.fullmatch(path) or ".." in path.split("/"):
        return None
    return f"{_base(dataset)}/{path}"


def _is_csv(resource: dict) -> bool:
    path = resource.get("path") if isinstance(resource.get("path"), str) else ""
    return resource.get("format") == "csv" or path.lower().endswith(".csv")


def _package(client, dataset: str) -> dict:
    resp = client.get(f"{_base(dataset)}/datapackage.json")
    if resp.status_code == 404:
        raise ValueError("dataset publishes no datapackage.json (some Core datasets ship datapackage.yml only).")
    resp.raise_for_status()
    package = resp.json()
    if not isinstance(package, dict):
        raise ValueError("datapackage.json is not an object.")
    return package


def _package_record(dataset: str, package: dict) -> dict:
    licenses = _licenses(package)
    resources = [
        {
            "name": resource.get("name"),
            "path": resource.get("path"),
            "format": resource.get("format"),
            "url": _resource_url(dataset, resource),
            "fields": [
                field.get("name")
                for field in ((resource.get("schema") or {}).get("fields") or [])
                if isinstance(field, dict)
            ],
        }
        for resource in package.get("resources") or []
        if isinstance(resource, dict)
    ]
    return {
        "entity": "DataPackage",
        "dataset": dataset,
        "name": package.get("name"),
        "title": package.get("title"),
        "description": package.get("description"),
        "last_updated": package.get("last_updated"),
        "license": _license_label(licenses),
        "licenses": licenses,
        "resources": resources,
        "datapackage_url": f"{_base(dataset)}/datapackage.json",
        "source_url": f"{CORE_URL}/{dataset}",
    }


def _pick_resource(package: dict, name) -> dict:
    resources = [r for r in package.get("resources") or [] if isinstance(r, dict) and _is_csv(r)]
    if name is None:
        if len(resources) != 1:
            raise ValueError("resource is required when a package has more than one CSV resource.")
        return resources[0]
    for resource in resources:
        if resource.get("name") == name:
            return resource
    raise ValueError("resource must name a CSV resource listed in datapackage.json.")


def run(input: dict, ctx) -> dict:
    operation = input.get("operation")
    if operation not in {"get-package", "fetch-resource"}:
        raise ValueError("a released DataHub Core operation is required")
    dataset = _dataset(input)
    with httpx.Client(headers={"User-Agent": UA}, timeout=60, follow_redirects=True) as client:
        package = _package(client, dataset)
        if operation == "get-package":
            return {"source_id": SOURCE_ID, "records": [_package_record(dataset, package)], "page": {}}
        limit = int(input.get("limit", 100))
        if not 1 <= limit <= 1000:
            raise ValueError("limit must be between 1 and 1000.")
        offset = int(input.get("offset", 0))
        if offset < 0:
            raise ValueError("offset must be zero or greater.")
        resource = _pick_resource(package, input.get("resource"))
        url = _resource_url(dataset, resource)
        if url is None:
            raise ValueError("resource path must be relative to the dataset.")
        license_label = _license_label(_licenses(package))
        records = []
        more = False
        with client.stream("GET", url) as resp:
            resp.raise_for_status()
            for index, row in enumerate(csv.DictReader(resp.iter_lines())):
                if index < offset:
                    continue
                if len(records) == limit:
                    more = True
                    break
                records.append({
                    "entity": "DataRow",
                    "dataset": dataset,
                    "resource": resource.get("name"),
                    "row_number": index + 1,
                    "values": dict(row),
                    "license": license_label,
                    "source_url": url,
                })
        return {
            "source_id": SOURCE_ID,
            "records": records,
            "page": {"returned": len(records), "limit": limit, "offset": offset,
                     "next_offset": offset + len(records) if more else None},
        }
