"""Everything the catalog shows about a repository, fetched in batches over GraphQL.

The first pass reads the repository's metadata, hacs.json and the two top levels of
custom_components; the second reads manifest.json for the integrations among them.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
import logging
from typing import Any

from .github import GitHub, OutOfTime

_LOGGER = logging.getLogger(__name__)

_REPO_FIELDS = """
  nameWithOwner description stargazerCount forkCount isArchived isFork isPrivate isDisabled isEmpty
  hasIssuesEnabled pushedAt createdAt url
  owner { login }
  parent { nameWithOwner }
  licenseInfo { spdxId name }
  repositoryTopics(first: 20) { nodes { topic { name } } }
  latestRelease { tagName publishedAt isPrerelease tagCommit { oid } }
  releases { totalCount }
  defaultBranchRef { name target { oid } }
  hacs: object(expression: "HEAD:hacs.json") { ... on Blob { text } }
  root: object(expression: "HEAD:") { ... on Tree { entries { name type } } }
  cc: object(expression: "HEAD:custom_components") { ... on Tree { entries {
    name type object { ... on Tree { entries { name type } } }
  } } }
"""


def _chunks(items: list[Any], size: int):
    for i in range(0, len(items), size):
        yield items[i:i + size]


def _alias_query(fields_by_alias: dict[str, str]) -> str:
    return "query {\n" + "\n".join(f"{a}: {f}" for a, f in fields_by_alias.items()) + "\n}"


def _owner_name(full_name: str) -> tuple[str, str]:
    owner, name = full_name.split("/", 1)
    return owner, name


def fetch_metadata(
    gh: GitHub, names: list[str], batch: int = 15, workers: int = 4
) -> dict[str, dict[str, Any]]:
    """GraphQL data per requested name; missing, private and moved-away ones are left out.

    A few batches run at once. GitHub asks for requests one at a time, but its
    secondary limit tolerates a handful, and one at a time takes an hour a night.
    """
    out: dict[str, dict[str, Any]] = {}
    chunks = list(_chunks(names, batch))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for n, part in enumerate(pool.map(lambda c: _metadata_batch(gh, c), chunks)):
            out.update(part)
            if n % 50 == 0:
                _LOGGER.info("metadata: %d of %d", min((n + 1) * batch, len(names)), len(names))
    return out


def _metadata_batch(gh: GitHub, chunk: list[str]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    fields = {}
    for i, full_name in enumerate(chunk):
        owner, name = _owner_name(full_name)
        fields[f"r{i}"] = (
            f"repository(owner: {json.dumps(owner)}, name: {json.dumps(name)}) {{{_REPO_FIELDS}}}"
        )
    try:
        data = gh.graphql(_alias_query(fields))
    except OutOfTime:
        return out
    except Exception as err:
        _LOGGER.warning("batch from %s failed (%s); trying one by one", chunk[0], str(err)[:120])
        data = {}
        for alias, field in fields.items():
            try:
                data.update(gh.graphql(_alias_query({alias: field})))
            except OutOfTime:
                break
            except Exception as err2:
                _LOGGER.warning("%s: %s", chunk[int(alias[1:])], err2)
    for i, full_name in enumerate(chunk):
        repo = data.get(f"r{i}")
        if repo:
            out[full_name] = repo
    return out


def fetch_manifests(gh: GitHub, wanted: dict[str, str], batch: int = 40) -> dict[str, str | None]:
    """manifest.json's text by repository, from the path given for each."""
    out: dict[str, str | None] = {}
    items = list(wanted.items())
    for chunk in _chunks(items, batch):
        fields = {}
        for i, (full_name, path) in enumerate(chunk):
            owner, name = _owner_name(full_name)
            fields[f"m{i}"] = (
                f"repository(owner: {json.dumps(owner)}, name: {json.dumps(name)}) "
                f"{{ object(expression: {json.dumps('HEAD:' + path)}) {{ ... on Blob {{ text }} }} }}"
            )
        try:
            data = gh.graphql(_alias_query(fields))
        except OutOfTime:
            break
        except Exception as err:
            _LOGGER.warning("manifest batch failed: %s", err)
            continue
        for i, (full_name, _) in enumerate(chunk):
            repo = data.get(f"m{i}") or {}
            out[full_name] = (repo.get("object") or {}).get("text")
    return out
