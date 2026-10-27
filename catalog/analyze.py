"""What a repository is, and how it fares against the checks HACS runs before it lists one.

The checks follow hacs/integration's validators (custom_components/hacs/validate),
read from the metadata already fetched rather than by running the HACS action, so
thousands of repositories cost a few hundred API calls a night. For repositories in
the queue the real HACS action has run on the pull request, and that result is kept
next to these.
"""

from __future__ import annotations

from datetime import UTC, datetime
import json
import math
from typing import Any

HACS_JSON_KEYS = {
    "content_in_root", "country", "filename", "hacs", "hide_default_branch",
    "homeassistant", "persistent_directory", "render_readme", "zip_release", "name",
}
MANIFEST_REQUIRED = ("codeowners", "documentation", "domain", "issue_tracker", "name", "version")
INFO_FILES = {"readme", "readme.md", "info", "info.md"}

# hacs/integration keeps a list of popular OSI-approved licences and looks the rest
# up in SPDX's list; this is that popular list and a few more, and anything else
# counts as not known rather than as failed.
OSI_LICENSES = {
    "0BSD", "AFL-3.0", "AGPL-3.0", "AGPL-3.0-only", "AGPL-3.0-or-later", "Apache-2.0",
    "Artistic-2.0", "BSD-2-Clause", "BSD-3-Clause", "BSD-3-Clause-Clear", "BSL-1.0",
    "ECL-2.0", "EPL-1.0", "EPL-2.0", "EUPL-1.1", "EUPL-1.2", "GPL-2.0", "GPL-2.0-only",
    "GPL-2.0-or-later", "GPL-3.0", "GPL-3.0-only", "GPL-3.0-or-later", "ISC",
    "LGPL-2.1", "LGPL-2.1-only", "LGPL-2.1-or-later", "LGPL-3.0", "LGPL-3.0-only",
    "LGPL-3.0-or-later", "LPPL-1.3c", "MIT", "MIT-0", "MPL-2.0", "MS-PL", "MS-RL",
    "MulanPSL-2.0", "NCSA", "OFL-1.1", "OSL-3.0", "PostgreSQL", "UPL-1.0", "Unlicense",
    "Zlib",
}


def parse_hacs_json(text: str | None) -> dict[str, Any] | None:
    if not text:
        return None
    try:
        value = json.loads(text)
    except ValueError:
        return None
    return value if isinstance(value, dict) else None


def _entries(obj: dict[str, Any] | None) -> list[dict[str, Any]]:
    return (obj or {}).get("entries") or []


def classify(repo: dict[str, Any], hint: str | None = None) -> dict[str, Any] | None:
    """Category, integration domain and content path; None when it is nothing HACS installs."""
    hacs = parse_hacs_json((repo.get("hacs") or {}).get("text")) or {}
    root = {e["name"]: e["type"] for e in _entries(repo.get("root"))}
    lower_root = {name.lower(): kind for name, kind in root.items()}
    filename = str(hacs.get("filename") or "")

    integration = None
    for entry in _entries(repo.get("cc")):
        if entry["type"] != "tree":
            continue
        files = {e["name"]: e for e in _entries(entry.get("object"))}
        if "manifest.json" in files:
            integration = {
                "domain": entry["name"],
                "path": f"custom_components/{entry['name']}",
                # A brand folder; HACS looks for brand/icon.png in it, and one
                # level more in every query costs more than it tells.
                "brand": (files.get("brand") or {}).get("type") == "tree",
            }
            break
    if integration is None and hacs.get("content_in_root") and "manifest.json" in root:
        integration = {"domain": None, "path": "", "brand": root.get("brand") == "tree"}

    if hint:
        category = hint
    elif integration:
        category = "integration"
    elif lower_root.get("themes") == "tree":
        category = "theme"
    elif lower_root.get("python_scripts") == "tree":
        category = "python_script"
    elif lower_root.get("apps") == "tree":
        category = "appdaemon"
    elif filename.endswith(".jinja"):
        category = "template"
    elif filename.endswith(".js") or lower_root.get("dist") == "tree" or any(
        n.endswith(".js") for n in lower_root
    ):
        category = "plugin"
    else:
        return None

    result: dict[str, Any] = {"category": category, "hacs": hacs}
    if category == "integration":
        if not integration:
            return None
        result.update(integration)
    return result


def run_checks(
    repo: dict[str, Any],
    kind: dict[str, Any],
    manifest: dict[str, Any] | None,
    brand_domains: set[str] | None,
) -> dict[str, bool | None]:
    """HACS's validators, by their own names; None where the answer is not known here."""
    root = {e["name"].lower() for e in _entries(repo.get("root"))}
    raw_hacs = parse_hacs_json((repo.get("hacs") or {}).get("text"))
    topics = [n["topic"]["name"] for n in (repo.get("repositoryTopics") or {}).get("nodes", [])]
    spdx = (repo.get("licenseInfo") or {}).get("spdxId")

    checks: dict[str, bool | None] = {
        "archived": not repo.get("isArchived"),
        "description": bool(repo.get("description")),
        "topics": bool(topics),
        "issues": bool(repo.get("hasIssuesEnabled")),
        "information": bool(root & INFO_FILES),
        "hacsjson": bool(
            raw_hacs is not None
            and isinstance(raw_hacs.get("name"), str)
            and set(raw_hacs) <= HACS_JSON_KEYS
            and not (raw_hacs.get("zip_release") and not raw_hacs.get("filename"))
        ),
        "license": (
            False if not spdx or spdx == "NOASSERTION" else (True if spdx in OSI_LICENSES else None)
        ),
    }
    if kind["category"] == "integration":
        checks["integration_manifest"] = bool(
            manifest
            and all(manifest.get(key) for key in MANIFEST_REQUIRED)
            and isinstance(manifest.get("codeowners"), list)
        )
        domain = kind.get("domain") or (manifest or {}).get("domain")
        if kind.get("brand") or (domain and brand_domains and domain in brand_domains):
            checks["brands"] = True
        else:
            checks["brands"] = None if brand_domains is None else False
    return checks


def _days_since(stamp: str | None, now: datetime) -> float | None:
    if not stamp:
        return None
    return (now - datetime.fromisoformat(stamp.replace("Z", "+00:00"))).total_seconds() / 86400


def score(entry: dict[str, Any], now: datetime | None = None) -> int:
    """A rough order for the list: liked, kept up, shipped, checked, nothing alarming."""
    now = now or datetime.now(UTC)
    points = math.log2(entry.get("stars", 0) + 1) * 10
    if entry.get("release"):
        points += 15
    checks = [v for v in (entry.get("checks") or {}).values() if v is not None]
    if checks:
        points += 20 * sum(checks) / len(checks)
    age = _days_since(entry.get("updated"), now)
    if age is not None:
        points += 15 if age <= 90 else 8 if age <= 365 else 0 if age <= 730 else -10
    pending = entry.get("pending") or {}
    if pending.get("checks") == "success":
        points += 10
    conflicts = entry.get("conflicts") or {}
    if conflicts.get("hacs"):
        points -= 15
    if conflicts.get("core"):
        points -= 5
    flags = (entry.get("scan") or {}).get("flags") or []
    points -= 25 * sum(1 for f in flags if f["severity"] == "high")
    points -= 5 * sum(1 for f in flags if f["severity"] == "medium")
    return round(points)
