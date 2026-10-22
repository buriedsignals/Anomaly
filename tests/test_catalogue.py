from __future__ import annotations

from pathlib import Path

import pytest

from anomaly import catalogue
from anomaly.detectors import registry


def _package(root: Path, name: str, *, release: str, parameters: str, bounds: str) -> Path:
    package = root / "user" / name
    package.mkdir(parents=True)
    (package / "meta.yaml").write_text(
        f"id: user.{name}\nversion: 1.0.0\nrelease: {release}\ntitle: {name}\n"
        "author: test\nlicense: CC0-1.0\ngroup: domain\ndescription: Test detector.\n"
        "required_tables: ['*']\nrequired_fields: [id]\n"
        f"parameters: {parameters}\nparameter_bounds: {bounds}\n"
        "signal_category: anomaly\nseverity: low\nexpected_output: [candidate_id]\n"
        "assumptions: [none]\nfalse_positives: [none]\nsensitive_output: redact\n"
        "resource_limits: {timeout_seconds: 5}\nquery: query.sql\n",
        encoding="utf-8",
    )
    (package / "query.sql").write_text(
        'SELECT CAST(id AS VARCHAR) AS candidate_id FROM "{{table_id}}" WHERE id >= ?\n',
        encoding="utf-8",
    )
    return package


def test_checked_in_catalogue_is_current() -> None:
    assert catalogue.main(["--check"]) == 0


def test_check_fails_when_checked_in_catalogue_is_stale(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    stale = tmp_path / "catalogue.json"
    stale.write_text(catalogue.render(catalogue.build_catalogue()).replace("1.1.0", "0.9.0"), encoding="utf-8")
    monkeypatch.setattr(catalogue, "CATALOGUE_PATH", stale)

    assert catalogue.main(["--check"]) == 1


def test_catalogue_lists_every_released_detector_not_a_bounded_slice() -> None:
    published = catalogue.build_catalogue()
    ids = [entry["id"] for entry in published["detectors"]]

    # The registry's default discovery slice stops at ten.
    assert len(ids) > len(registry.discover_detectors())
    assert ids == sorted(ids)
    assert published["schema_version"] == catalogue.SCHEMA_VERSION
    assert published["catalogue_hash"].startswith("sha256:")


def test_catalogue_excludes_template_and_draft_packages(tmp_path: Path) -> None:
    _package(tmp_path, "shipped", release="released", parameters="{minimum: 1}",
             bounds="{minimum: {type: integer, minimum: 0, maximum: 10}}")
    _package(tmp_path, "unfinished", release="draft", parameters="{minimum: 1}",
             bounds="{minimum: {type: integer, minimum: 0, maximum: 10}}")
    template = tmp_path / "_template"
    template.mkdir()
    (template / "meta.yaml").write_text("id: user.template\nrelease: released\n", encoding="utf-8")

    entries = catalogue.build_catalogue(tmp_path)["detectors"]

    assert [entry["id"] for entry in entries] == ["user.shipped"]
    assert entries[0]["parameters"] == {
        "minimum": {"default": 1, "type": "integer", "minimum": 0, "maximum": 10}
    }
    assert entries[0]["required_fields"] == [{"name": "id", "types": None}]


@pytest.mark.parametrize(
    ("parameters", "bounds"),
    [
        ("{minimum: 1}", "{}"),
        ("{minimum: 50}", "{minimum: {type: integer, minimum: 0, maximum: 10}}"),
        ("{minimum: 1.5}", "{minimum: {type: integer, minimum: 0, maximum: 10}}"),
        ("{minimum: 1}", "{minimum: {type: integer, minimum: 0}}"),
    ],
    ids=["missing-bound", "default-out-of-range", "default-wrong-type", "incomplete-bound"],
)
def test_catalogue_refuses_released_detector_without_valid_parameter_bounds(
    tmp_path: Path, parameters: str, bounds: str
) -> None:
    _package(tmp_path, "shipped", release="released", parameters=parameters, bounds=bounds)

    with pytest.raises(catalogue.CatalogueError):
        catalogue.build_catalogue(tmp_path)
