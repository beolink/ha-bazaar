"""Where the candidates come from: the HACS queue and GitHub's code search.

The default lists and the removed list are read from hacs/default itself, so a
repository HACS already carries, or has thrown out, never reaches the catalog.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
import json
import logging
import re
from typing import Any

from .github import GitHub

_LOGGER = logging.getLogger(__name__)

RAW_DEFAULT = "https://raw.githubusercontent.com/hacs/default/master"

# HACS's own names. "plugin" is what the store shows as Dashboard.
CATEGORIES = ("integration", "plugin", "theme", "template", "python_script", "appdaemon")

_REPO = r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})/[A-Za-z0-9._-]{1,100}"
_TITLE_BRACKET = re.compile(r"\[\s*'?(" + _REPO + r")'?\s*\]")
_TITLE_ANY = re.compile(r"(?<![\w/.-])(" + _REPO + r")(?![\w/-])")
_DIFF_ADDED = re.compile(r'^\+\s*"(' + _REPO + r')",?\s*$', re.MULTILINE)


@dataclass
class Pending:
    """An open pull request that asks HACS to add a repository."""

    number: int
    category: str
    created_at: str
    url: str
    checks: str | None = None
    failed: list[str] = field(default_factory=list)


def norm(full_name: str) -> str:
    return full_name.strip().strip("/").lower()


def load_default(gh: GitHub) -> dict[str, str]:
    """Every repository in the HACS default lists, lowercased, to its category."""
    known: dict[str, str] = {}
    for category in (*CATEGORIES, "netdaemon"):
        for name in json.loads(gh.raw(f"{RAW_DEFAULT}/{category}")):
            known[norm(name)] = category
    return known


HACS_DATA = "https://data-v2.hacs.xyz/{category}/data.json"


def load_hacs_data(gh: GitHub) -> tuple[set[str], dict[str, str]]:
    """What HACS serves its users: names after renames, and each integration's domain.

    The lists in hacs/default keep the name a repository was added under; HACS's
    own data follows it when it is renamed.
    """
    names: set[str] = {"hacs/integration"}
    domains: dict[str, str] = {}
    for category in CATEGORIES:
        for item in json.loads(gh.raw(HACS_DATA.format(category=category))).values():
            if full_name := item.get("full_name"):
                names.add(norm(full_name))
                if category == "integration" and item.get("domain"):
                    domains.setdefault(item["domain"], full_name)
    return names, domains


def load_removed(gh: GitHub) -> dict[str, dict[str, Any]]:
    """Repositories HACS has removed, blacklisted or marked critical."""
    removed: dict[str, dict[str, Any]] = {}
    for entry in json.loads(gh.raw(f"{RAW_DEFAULT}/removed")):
        removed[norm(entry["repository"])] = entry
    for name in json.loads(gh.raw(f"{RAW_DEFAULT}/blacklist")):
        removed.setdefault(norm(name), {"repository": name, "removal_type": "blacklist"})
    for entry in json.loads(gh.raw(f"{RAW_DEFAULT}/critical")):
        removed[norm(entry["repository"])] = {**entry, "removal_type": "critical"}
    return removed


_PULLS_QUERY = """
query($cursor: String) {
  repository(owner: "hacs", name: "default") {
    pullRequests(states: OPEN, first: 20, after: $cursor, orderBy: {field: CREATED_AT, direction: ASC}) {
      pageInfo { hasNextPage endCursor }
      nodes {
        number title createdAt url
        files(first: 10) { nodes { path additions deletions } }
        commits(last: 1) { nodes { commit { statusCheckRollup { contexts(first: 40) { nodes {
          __typename
          ... on CheckRun { name conclusion status startedAt }
          ... on StatusContext { context state createdAt }
        } } } } } }
      }
    }
  }
}
"""

# Runs that only report on the others, or that say nothing about the repository.
_IGNORED_CHECKS = {"action checks completed", "editable pr", "sorted", "jq", "json schema"}


def summarize_checks(contexts: list[dict[str, Any]]) -> tuple[str | None, list[str]]:
    """The newest run of each check decides; a PR's re-runs leave cancelled ones behind.

    Only a completed success counts as passed. A run that was cancelled, never
    started or waits for approval leaves the check open.
    """
    latest: dict[str, tuple[str, str]] = {}
    for node in contexts:
        if node.get("__typename") == "CheckRun":
            name = node.get("name") or ""
            # A queued re-run has no start time yet and is the newest of all.
            started = node.get("startedAt") or "~"
            result = (node.get("conclusion") or "PENDING") if node.get("status") == "COMPLETED" else "PENDING"
        else:
            name, started = node.get("context") or "", node.get("createdAt") or "~"
            result = node.get("state") or "PENDING"
        if not name or name.lower() in _IGNORED_CHECKS:
            continue
        if name not in latest or started >= latest[name][0]:
            latest[name] = (started, result)
    if not latest:
        return None, []
    failed = sorted(n for n, (_, r) in latest.items() if r in ("FAILURE", "ERROR", "TIMED_OUT"))
    if failed:
        return "failure", failed
    if all(r in ("SUCCESS", "NEUTRAL", "SKIPPED") for _, r in latest.values()):
        return "success", []
    return "pending", []


def repo_from_title(title: str) -> str | None:
    if match := _TITLE_BRACKET.search(title):
        return match.group(1).rstrip(".")
    # A full stop may end the sentence the name stands in; GitHub names never end in one.
    candidates = [m.rstrip(".") for m in _TITLE_ANY.findall(title) if not m.lower().startswith("hacs/")]
    return candidates[0] if len(candidates) == 1 else None


def load_pending(gh: GitHub) -> dict[str, tuple[str, Pending]]:
    """Open pull requests to hacs/default that add one repository, by lowercased name."""
    pending: dict[str, tuple[str, Pending]] = {}
    cursor = None
    while True:
        data = gh.graphql(_PULLS_QUERY, {"cursor": cursor})
        page = data["repository"]["pullRequests"]
        for pr in page["nodes"]:
            added = [
                f["path"] for f in pr["files"]["nodes"]
                if f["path"] in CATEGORIES and f["additions"] > f["deletions"]
            ]
            # Renames, removals and workflow bumps add nothing to a list. A rename
            # swaps one line for another, so it adds no more than it deletes.
            # The title is no guide: GitHub's editor calls an addition "Update integration".
            if len(added) != 1:
                continue
            title_repo = repo_from_title(pr["title"])
            repos = [title_repo] if title_repo else []
            if not repos or len(pr["files"]["nodes"]) != 1:
                repos = _repos_from_diff(gh, pr["number"])
            commits = pr["commits"]["nodes"]
            rollup = commits[0]["commit"].get("statusCheckRollup") if commits else None
            checks, failed = summarize_checks(rollup["contexts"]["nodes"] if rollup else [])
            for repo in repos:
                entry = Pending(pr["number"], added[0], pr["createdAt"], pr["url"], checks, failed)
                # Several PRs for one repository: the newest is the one that counts.
                pending[norm(repo)] = (repo, entry)
        if not page["pageInfo"]["hasNextPage"]:
            break
        cursor = page["pageInfo"]["endCursor"]
    _LOGGER.info("%d repositories wait in the HACS queue", len(pending))
    return pending


def _repos_from_diff(gh: GitHub, number: int) -> list[str]:
    files = gh.rest(f"/repos/hacs/default/pulls/{number}/files")
    found: list[str] = []
    for f in files:
        if f.get("filename") in CATEGORIES:
            found += _DIFF_ADDED.findall(f.get("patch") or "")
    return found


def size_ranges(gh: GitHub, low: int = 0, high: int = 4096, cap: int = 1000):
    """Split hacs.json's byte size into ranges that each stay under search's cap of 1,000 hits.

    Yields (range, first page) so the probe that measured a range is also its first page.
    """
    stack = [(low, high)]
    while stack:
        lo, hi = stack.pop()
        first = gh.code_search(_hacs_query(lo, hi))
        total = first.get("total_count", 0)
        if total > cap and hi > lo:
            mid = (lo + hi) // 2
            stack += [(mid + 1, hi), (lo, mid)]
            continue
        if total > cap:
            _LOGGER.warning("%d hacs.json files of %d bytes; search shows only %d", total, lo, cap)
        yield (lo, hi), first


def _hacs_query(lo: int, hi: int) -> str:
    return f"filename:hacs.json path:/ size:{lo}..{hi}"


def code_search_candidates(gh: GitHub, high: int = 4096) -> Iterator[str]:
    """Repositories with a hacs.json at the root, each name once.

    A generator, so a search that stops halfway still leaves what it found.
    GitHub's index leaves out most forks, and is incomplete at the edges; what it
    misses is found again the next night or not at all, which the catalog can live with.
    """
    found: set[str] = set()
    for (lo, hi), first in size_ranges(gh, 0, high):
        page, result = 1, first
        while True:
            for item in result.get("items", []):
                if item.get("path") != "hacs.json":
                    continue
                name = item["repository"]["full_name"]
                if norm(name) not in found:
                    found.add(norm(name))
                    yield name
            total = min(result.get("total_count", 0), 1000)
            if page * 100 >= total or not result.get("items"):
                break
            page += 1
            result = gh.code_search(_hacs_query(lo, hi), page)
        _LOGGER.info("hacs.json %d..%d bytes: %d repositories so far", lo, hi, len(found))
