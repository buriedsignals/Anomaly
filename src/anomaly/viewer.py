"""Self-contained evidence viewer rendered from hash-bound Gate-B artifacts.

The viewer is a post-report enrichment of P7, mirroring :mod:`anomaly.report`:
it reads only accepted findings and the replayed evidence bound by the Gate-B
receipt, embeds them as a redacted JSON payload inside one static HTML file,
and records a sha256 receipt so regeneration is verifiable and byte-
deterministic.  No network access, no external assets, no timestamps.

Every case-controlled string reaches the page through one JSON payload that is
escaped for inline embedding and rendered with ``textContent`` only, so
hostile case content can neither break out of the script element nor inject
markup.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from anomaly.events import phase_event
from anomaly.report import ChartError, _atomic_write, _gate_b_artifacts
from anomaly.review import _hash_json, _owned, _root
from anomaly.semantics import redact_credentials

__all__ = ["ViewerError", "generate_viewer"]

_VIEWER_PATH = "findings/viewer.html"
_RECEIPT_PATH = ".anomaly/receipts/viewer.json"


class ViewerError(RuntimeError):
    """An evidence-viewer contract was not satisfied."""


@phase_event("P7", "generate_viewer")
def generate_viewer(root: Path) -> dict[str, Any]:
    """Render the self-contained evidence viewer from Gate-B accepted findings.

    Refuses without writing anything unless ``.anomaly/receipts/gate-b.json``
    exists and still binds the current findings, review, and replay artifacts.
    """
    root = _root(root)
    try:
        gate_b = _gate_b_artifacts(root)
    except ChartError as error:
        raise ViewerError(str(error)) from error

    payload = _viewer_payload(gate_b, _unresolved_text(root))
    blob = _document(payload).encode("utf-8")

    viewer_path = _owned(root, _VIEWER_PATH)
    viewer_path.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write(viewer_path, blob)

    manifest = {
        "kind": "viewer",
        "gate": "B",
        "findings_identity": "findings/findings.json",
        "findings_hash": gate_b["receipt"]["findings_hash"],
        "replay_identity": "evidence/replay.json",
        "replay_hash": _hash_json(gate_b["replay"]),
        "viewer": _VIEWER_PATH,
        "viewer_hash": "sha256:" + hashlib.sha256(blob).hexdigest(),
        "notes": {
            "text": (
                "All viewer text passes the case redaction filter; the payload "
                "is escaped for inline embedding and rendered via textContent; "
                "keys are sorted and no timestamp enters the output."
            ),
        },
    }
    _atomic_write(
        _owned(root, _RECEIPT_PATH),
        (json.dumps(manifest, sort_keys=True, indent=2) + "\n").encode("utf-8"),
    )
    return manifest


def _viewer_payload(gate_b: dict[str, Any], unresolved_text: str) -> dict[str, Any]:
    """Build the redacted, deterministically ordered viewer payload."""
    findings = gate_b["findings"]
    review = gate_b["review"]
    replay_claims = [
        signal
        for signal in gate_b["replay"].get("claims", [])
        if isinstance(signal, dict)
    ]
    signals_by_id = {
        signal["signal_id"]: signal
        for signal in replay_claims
        if isinstance(signal.get("signal_id"), str)
    }
    verdicts = review.get("verdicts") if isinstance(review.get("verdicts"), dict) else {}

    claims = []
    for claim in findings.get("claims", []):
        if not isinstance(claim, dict):
            continue
        signals = []
        for signal_id in claim.get("signal_ids", []):
            signal = signals_by_id.get(signal_id)
            if isinstance(signal, dict):
                signals.append(_signal_view(signal))
        verdict = verdicts.get(claim["claim_id"])
        claims.append(
            {
                "claim_id": claim.get("claim_id"),
                "statement": claim.get("statement"),
                "rank": claim.get("rank"),
                "status": claim.get("status"),
                "category": claim.get("category"),
                "categories": claim.get("categories", []),
                "calculation": claim.get("calculation"),
                "evidence_refs": claim.get("evidence_refs", []),
                "provenance": claim.get("provenance", []),
                "signals": sorted(signals, key=lambda item: str(item["signal_id"])),
                "review": _verdict_view(verdict),
            }
        )
    claims.sort(key=lambda item: (item["rank"] if isinstance(item["rank"], int) else 0, str(item["claim_id"])))

    return _redact(
        {
            "claims": claims,
            "reviewer": _reviewer_view(review),
            "alternatives": review.get("alternatives", []),
            "unavailable_inputs": review.get("unavailable_inputs", []),
            "replay_gaps": review.get("replay_gaps", []),
            "unresolved_questions": review.get("unresolved_questions", []),
            "unresolved_markdown": unresolved_text,
        }
    )


def _signal_view(signal: dict[str, Any]) -> dict[str, Any]:
    return {
        "signal_id": signal.get("signal_id"),
        "statement": signal.get("statement"),
        "category": signal.get("category"),
        "severity": signal.get("severity"),
        "preview": signal.get("preview"),
        "detector_id": signal.get("detector_id"),
        "run_id": signal.get("run_id"),
        "source_hash": signal.get("source_hash"),
        "detector_hash": signal.get("detector_hash"),
        "evidence_refs": signal.get("evidence_refs", []),
        "calculation": signal.get("calculation"),
    }


def _verdict_view(verdict: Any) -> dict[str, Any]:
    if not isinstance(verdict, dict):
        return {"verdict": None, "notes": None}
    return {
        "verdict": verdict.get("verdict"),
        "notes": verdict.get("notes"),
    }


def _reviewer_view(review: dict[str, Any]) -> dict[str, Any]:
    attestation = review.get("independent_attestation")
    attestation = attestation if isinstance(attestation, dict) else {}
    return {
        "reviewer_id": review.get("reviewer_id"),
        "attested_by": attestation.get("attested_by"),
        "isolated": attestation.get("isolated"),
        "statement": attestation.get("statement"),
    }




def _unresolved_text(root: Path) -> str:
    """Read the redacted unresolved-work notes; absent means empty."""
    unresolved = _owned(root, "findings/unresolved.md")
    if not unresolved.is_file() or unresolved.is_symlink():
        return ""
    return redact_credentials(unresolved.read_text(encoding="utf-8"))


def _redact(value: Any) -> Any:
    """Apply the case redaction filter to every string in the payload."""
    if isinstance(value, str):
        return redact_credentials(value)
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, dict):
        return {key: _redact(item) for key, item in value.items()}
    return value


def _document(payload: dict[str, Any]) -> str:
    """Render the static page around one safely embedded JSON payload."""
    embedded = (
        json.dumps(payload, sort_keys=True, indent=2)
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
        .replace("\\u2028", "\\u2028")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )
    return (
        "<!doctype html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        "<title>Anomaly evidence viewer</title>\n"
        "<style>\n"
        ":root{--ink:#080808;--muted:#565656;--line:#cfcfcf;--soft:#f3f3f3}\n"
        "*{box-sizing:border-box}\n"
        "body{margin:0;background:#fff;color:var(--ink);"
        "font-family:Arial,Helvetica,sans-serif;line-height:1.5}\n"
        "code,.mono{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;"
        "font-size:.85em}\n"
        "header{border-bottom:1px solid var(--ink);padding:1.25rem 1.5rem}\n"
        "h1{margin:0;font-size:1.4rem;letter-spacing:-0.02em}\n"
        ".sub{margin:.35rem 0 0;color:var(--muted);font-size:.9rem}\n"
        "main{display:grid;grid-template-columns:20rem minmax(0,1fr);"
        "gap:1.5rem;padding:1.5rem;max-width:70rem;margin:0 auto}\n"
        "#claim-list{display:flex;flex-direction:column;gap:.4rem;"
        "align-self:start;position:sticky;top:1rem}\n"
        "#claim-list button{all:unset;cursor:pointer;border:1px solid var(--line);"
        "padding:.55rem .7rem;font:inherit;font-size:.85rem}\n"
        "#claim-list button[aria-current=\"true\"]{background:var(--ink);"
        "color:#fff;border-color:var(--ink)}\n"
        "article{border:1px solid var(--ink);padding:1.1rem 1.25rem;margin:0 0 1.5rem}\n"
        "h2{margin:.2rem 0 1rem;font-size:1.15rem;letter-spacing:-0.02em}\n"
        "h3{margin:1.25rem 0 .5rem;font-size:.95rem}\n"
        "dl{display:grid;grid-template-columns:9rem minmax(0,1fr);"
        "gap:.4rem 1rem;margin:0}\n"
        "dt{color:var(--muted);font-size:.8rem;text-transform:uppercase;"
        "font-family:ui-monospace,Menlo,monospace}\n"
        "dd{margin:0;min-width:0;overflow-wrap:break-word}\n"
        "pre{background:var(--soft);border:1px solid var(--line);padding:.75rem;"
        "overflow:auto;white-space:pre-wrap}\n"
        "ul{margin:.25rem 0;padding-left:1.1rem}\n"
        "@media (max-width:760px){main{display:block}#claim-list{position:static;"
        "margin-bottom:1.5rem}}\n"
        "@media print{#claim-list{display:none}main{display:block}}\n"
        "</style>\n"
        "</head>\n"
        "<body>\n"
        "<header>\n"
        "<h1>Anomaly evidence viewer</h1>\n"
        '<p class="sub">Every accepted claim with its evidence chain. '
        "Generated at Gate B; findings are journalist-approved, signals are leads "
        "with recorded provenance.</p>\n"
        "</header>\n"
        "<main>\n"
        '<nav id="claim-list" aria-label="Accepted findings"></nav>\n'
        "<div>\n"
        '<section id="detail" aria-live="polite"></section>\n'
        '<section id="context"><h2>Independent review context</h2></section>\n'
        '<section id="unresolved"><h2>Unresolved work</h2>'
        '<pre id="unresolved-text"></pre></section>\n'
        "</div>\n"
        "</main>\n"
        '<script type="application/json" id="viewer-data">' + embedded + "</script>\n"
        "<script>\n"
        '"use strict";\n'
        'var payload = JSON.parse(document.getElementById("viewer-data").textContent);\n'
        'function cell(tag, value){var node = document.createElement(tag);'
        "if (value !== null && value !== undefined) { node.textContent = String(value); }"
        "return node;}\n"
        'function row(list, label, value){if (value === null || value === undefined || value === "")'
        "{return;} list.appendChild(cell(\"dt\", label)); list.appendChild(cell(\"dd\", value));}\n"
        'function definitionList(entries){var dl = document.createElement(\"dl\");'
        "for (const entry of entries){row(dl, entry[0], entry[1]);} return dl;}\n"
        'function codeBlock(value){var pre = document.createElement(\"pre\");'
        'pre.textContent = JSON.stringify(value, null, 2); return pre;}\n'
        'var list = document.getElementById(\"claim-list\");\n'
        'var detail = document.getElementById(\"detail\");\n'
        'payload.claims.forEach(function(claim, index){\n'
        '  var button = document.createElement(\"button\");\n'
        '  button.type = \"button\";\n'
        '  button.textContent = (claim.rank || index + 1) + \" · \" + claim.claim_id;\n'
        '  button.addEventListener(\"click\", function(){show(claim, button);});\n'
        '  list.appendChild(button);\n'
        "});\n"
        'function show(claim, button){\n'
        '  for (const node of list.children){node.removeAttribute(\"aria-current\");}\n'
        '  if (button){button.setAttribute(\"aria-current\", \"true\");}\n'
        '  detail.textContent = "";\n'
        '  var article = document.createElement(\"article\");\n'
        '  var heading = document.createElement(\"h2\");\n'
        '  heading.textContent = claim.statement || claim.claim_id;\n'
        '  article.appendChild(heading);\n'
        '  article.appendChild(definitionList([\n'
        '    [\"Claim\", claim.claim_id], [\"Status\", claim.status],\n'
        '    [\"Rank\", claim.rank], [\"Category\", (claim.categories || []).join(\", \") || claim.category],\n'
        '    [\"Review verdict\", claim.review ? claim.review.verdict : null],'
        ' [\"Reviewer notes\", claim.review ? claim.review.notes : null]\n'
        "  ]));\n"
        '  var signalsHeading = document.createElement(\"h3\");\n'
        '  signalsHeading.textContent = \"Supporting signals\";\n'
        '  article.appendChild(signalsHeading);\n'
        '  (claim.signals || []).forEach(function(signal){\n'
        '    var box = document.createElement(\"div\");\n'
        '    var title = document.createElement(\"p\");\n'
        '    title.textContent = signal.statement || signal.signal_id;\n'
        '    box.appendChild(title);\n'
        '    box.appendChild(definitionList([\n'
        '      [\"Signal\", signal.signal_id], [\"Detector\", signal.detector_id],'
        ' [\"Severity\", signal.severity], [\"Run\", signal.run_id],\n'
        '      [\"Source hash\", signal.source_hash], [\"Detector hash\", signal.detector_hash],'
        ' [\"Replay status\", \"replayed\"]\n'
        "    ]));\n"
        '    if (signal.evidence_refs && signal.evidence_refs.length){\n'
        '      var refs = document.createElement(\"h4\");\n'
        '      refs.textContent = \"Evidence references\";\n'
        '      box.appendChild(refs);\n'
        '      box.appendChild(codeBlock(signal.evidence_refs));\n'
        "    }\n"
        '    if (signal.calculation){\n'
        '      var calc = document.createElement(\"h4\");\n'
        '      calc.textContent = \"Replayed calculation\";\n'
        '      box.appendChild(calc);\n'
        '      box.appendChild(codeBlock(signal.calculation));\n'
        "    }\n"
        '    if (signal.preview){\n'
        '      var preview = document.createElement(\"h4\");\n'
        '      preview.textContent = \"Redacted preview\";\n'
        '      box.appendChild(preview);\n'
        '      box.appendChild(codeBlock(signal.preview));\n'
        "    }\n"
        '    article.appendChild(box);\n'
        "  });\n"
        '  if (claim.provenance && claim.provenance.length){\n'
        '    var prov = document.createElement(\"h3\");\n'
        '    prov.textContent = \"Detector provenance\";\n'
        '    article.appendChild(prov);\n'
        '    article.appendChild(codeBlock(claim.provenance));\n'
        "  }\n"
        '  detail.appendChild(article);\n'
        "}\n"
        'if (payload.claims.length){list.children[0].click();}\n'
        'var context = document.querySelector(\"#context\");\n'
        'var reviewer = payload.reviewer || {};\n'
        'context.appendChild(definitionList([\n'
        '  [\"Reviewer\", reviewer.reviewer_id], [\"Attested by\", reviewer.attested_by],'
        ' [\"Isolated\", reviewer.isolated], [\"Attestation\", reviewer.statement],\n'
        '  [\"Alternative explanations\", (payload.alternatives || []).join(\"; \") || null],\n'
        '  [\"Unavailable inputs\", (payload.unavailable_inputs || []).join(\"; \") || null],\n'
        '  [\"Replay gaps\", (payload.replay_gaps || []).join(\"; \") || null],\n'
        '  [\"Unresolved questions\", (payload.unresolved_questions || []).join(\"; \") || null]\n'
        "]));\n"
        'document.getElementById(\"unresolved-text\").textContent ='
        ' payload.unresolved_markdown || \"No unresolved work was recorded.\";\n'
        "</script>\n"
        "</body>\n"
        "</html>\n"
    )
