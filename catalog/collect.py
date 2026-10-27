"""Build catalog.json: every repository HACS could install but does not list.

    python -m catalog.collect --out site/catalog.json --previous https://.../scan-cache.json

Next to the catalog goes scan-cache.json, which only the next night reads: an
integration whose release, folder and requirements have not changed keeps the
scan it got last time, so a night costs a scan per change.

With --budget a night that GitHub slows down stops each part in time and
publishes what it has, marked in "incomplete", instead of being cut off by the
workflow's timeout with nothing to show.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
import hashlib
import json
import logging
from pathlib import Path
import sys
import time
from typing import Any
import urllib.parse
import urllib.request

from . import analyze, scan
from .github import GitHub, GitHubError, find_token
from .inspect import fetch_manifests, fetch_metadata
from .sources import (
    Pending,
    code_search_candidates,
    load_default,
    load_hacs_data,
    load_pending,
    load_removed,
    norm,
)

_LOGGER = logging.getLogger("catalog")

SCHEMA = 1
CACHE_NAME = "scan-cache.json"
BRANDS_DOMAINS = "https://brands.home-assistant.io/domains.json"
TARBALL = "https://codeload.github.com/{repo}/tar.gz/{ref}"
TARBALL_LIMIT = 30_000_000
RELEASE_ASSET = "https://github.com/{repo}/releases/download/{tag}/{filename}"
DENYLIST = Path(__file__).resolve().parent.parent / "denylist.json"


def load_denylist(path: Path = DENYLIST) -> set[str]:
    """Repositories left out on request, mostly by their own authors."""
    try:
        entries = json.loads(path.read_text())
    except FileNotFoundError:
        return set()
    return {norm(e["repository"] if isinstance(e, dict) else e) for e in entries}


def _load_json(source: str | None) -> Any:
    if not source:
        return None
    try:
        if source.startswith(("http://", "https://")):
            with urllib.request.urlopen(source, timeout=60) as response:
                return json.loads(response.read())
        return json.loads(Path(source).read_text())
    except (OSError, ValueError) as err:
        _LOGGER.warning("no previous catalog from %s (%s)", source, err)
        return None


def _brand_domains(gh: GitHub) -> tuple[set[str] | None, set[str]]:
    """Custom domains with icons in home-assistant/brands, and Home Assistant's own domains.

    The custom set is None when the list is unavailable, so the brands check is
    unknown that night rather than failed.
    """
    try:
        domains = json.loads(gh.raw(BRANDS_DOMAINS))
    except Exception as err:
        _LOGGER.warning("brands list unavailable, the brands check is unknown tonight: %s", err)
        return None, set()
    return set(domains.get("custom", [])), set(domains.get("core", []))


def _manifest(text: str | None) -> dict[str, Any] | None:
    try:
        value = json.loads(text) if text else None
    except ValueError:
        return None
    return value if isinstance(value, dict) else None


def _icon(repo: str, kind: dict[str, Any], domain: str | None, brands: set[str] | None, ref: str) -> str | None:
    if kind.get("brand"):
        base = f"{kind['path']}/brand" if kind.get("path") else "brand"
        return f"https://raw.githubusercontent.com/{repo}/{ref}/{base}/icon.png"
    if domain and brands and domain in brands:
        return f"https://brands.home-assistant.io/_/{domain}/icon.png"
    return None


def build_entry(
    repo: dict[str, Any],
    kind: dict[str, Any],
    pending: Pending | None,
    manifest: dict[str, Any] | None,
    brands: set[str] | None,
) -> dict[str, Any]:
    full_name = repo["nameWithOwner"]
    hacs = kind.get("hacs") or {}
    domain = kind.get("domain") or (manifest or {}).get("domain")
    release = repo.get("latestRelease")
    branch = repo.get("defaultBranchRef") or {}
    entry: dict[str, Any] = {
        "repo": full_name,
        "category": kind["category"],
        "name": str(hacs.get("name") or (manifest or {}).get("name") or full_name.split("/")[1]),
        "description": repo.get("description") or "",
        "stars": repo.get("stargazerCount", 0),
        "topics": [n["topic"]["name"] for n in (repo.get("repositoryTopics") or {}).get("nodes", [])],
        "license": (repo.get("licenseInfo") or {}).get("spdxId"),
        "updated": repo.get("pushedAt"),
        "created": repo.get("createdAt"),
        "releases": (repo.get("releases") or {}).get("totalCount", 0),
        "release": (
            {"tag": release["tagName"], "date": release["publishedAt"],
             "commit": (release.get("tagCommit") or {}).get("oid")}
            if release else None
        ),
        "branch": branch.get("name"),
        "commit": (branch.get("target") or {}).get("oid"),
        "checks": analyze.run_checks(repo, kind, manifest, brands),
    }
    if domain:
        entry["domain"] = domain
    if kind.get("path") is not None and kind["category"] == "integration":
        entry["path"] = kind["path"]
    if hacs.get("homeassistant"):
        entry["homeassistant"] = str(hacs["homeassistant"])
    if hacs.get("zip_release"):
        entry["zip_release"] = str(hacs.get("filename") or "")
    if repo.get("isFork") and repo.get("parent"):
        entry["fork_of"] = repo["parent"]["nameWithOwner"]
    if pending:
        entry["pending"] = {
            "pr": pending.number, "since": pending.created_at,
            "checks": pending.checks, "failed": pending.failed,
        }
    ref = entry["release"]["tag"] if entry["release"] else (entry["branch"] or "HEAD")
    if icon := _icon(full_name, kind, domain, brands, ref):
        entry["icon"] = icon
    if manifest and kind["category"] == "integration":
        entry["requirements"] = [r for r in manifest.get("requirements") or [] if isinstance(r, str)][:20]
    return entry


def for_clients(entry: dict[str, Any]) -> dict[str, Any]:
    """What the website and the panel read: checks as the ones that failed, no build-only fields.

    The catalog is downloaded by every Home Assistant that runs the panel, so
    every field here is paid for thousands of times over.
    """
    build_only = ("checks", "branch", "commit", "requirements", "path", "zip_release", "releases")
    out = {k: v for k, v in entry.items() if k not in build_only}
    checks = entry.get("checks") or {}
    if failed := [k for k, v in checks.items() if v is False]:
        out["failed"] = failed
    if unknown := [k for k, v in checks.items() if v is None]:
        out["unknown"] = unknown
    if out.get("release"):
        out["release"] = {"tag": out["release"]["tag"], "date": out["release"]["date"]}
    if scan_result := out.get("scan"):
        # GitHub takes a commit by its first characters in a link; the key is for the cache file.
        scan_result = {k: v for k, v in scan_result.items() if k not in ("key", "lines")}
        if scan_result.get("ref"):
            scan_result["ref"] = scan_result["ref"][:12]
        out["scan"] = scan_result
    out["topics"] = out.get("topics", [])[:8]
    if not out["topics"]:
        del out["topics"]
    if out.get("pending") and not out["pending"].get("failed"):
        out["pending"] = {k: v for k, v in out["pending"].items() if k != "failed"}
    if not out.get("description"):
        out.pop("description", None)
    return out


def _scan_ref(entry: dict[str, Any]) -> str | None:
    """What HACS would install: the latest release, else the default branch."""
    if entry.get("release") and entry["release"].get("commit"):
        return entry["release"]["commit"]
    return entry.get("commit")


def mark_conflicts(entries: list[dict[str, Any]], hacs_domains: dict[str, str], core_domains: set[str]) -> None:
    """Integrations whose domain is taken: Home Assistant loads only one of each.

    Mostly copies and alternative versions of something HACS or Home Assistant
    already has. Installing one beside the other makes one of them disappear.
    """
    counts: dict[str, int] = {}
    for entry in entries:
        if entry["category"] == "integration" and entry.get("domain"):
            counts[entry["domain"]] = counts.get(entry["domain"], 0) + 1
    for entry in entries:
        domain = entry.get("domain")
        if entry["category"] != "integration" or not domain:
            continue
        conflicts: dict[str, Any] = {}
        if domain in hacs_domains and norm(hacs_domains[domain]) != norm(entry["repo"]):
            conflicts["hacs"] = hacs_domains[domain]
        if domain in core_domains:
            conflicts["core"] = True
        if counts[domain] > 1:
            conflicts["shared"] = counts[domain] - 1
        if conflicts:
            entry["conflicts"] = conflicts


def scan_key(entry: dict[str, Any], manifest: dict[str, Any] | None) -> str | None:
    """What a cached scan depends on: the rules, the commit, the folder and the requirements.

    None when the manifest could not be read, since its requirements are part of
    the result; such a scan is redone the next night instead of kept.
    """
    ref = _scan_ref(entry)
    if not ref or manifest is None:
        return None
    requirements = json.dumps(sorted(r for r in manifest.get("requirements") or [] if isinstance(r, str)))
    digest = hashlib.sha256(requirements.encode()).hexdigest()[:12]
    source = f"zip:{entry['zip_release']}" if entry.get("zip_release") is not None else entry.get("path", "")
    return f"{scan.SCAN_VERSION}:{ref}:{source}:{digest}"


def scan_entry(gh: GitHub, entry: dict[str, Any], manifest: dict[str, Any] | None) -> dict[str, Any]:
    ref = _scan_ref(entry)
    key = scan_key(entry, manifest)
    if not ref:
        return {"ref": None, "error": "no commit"}
    asset = entry.get("zip_release")
    if asset is not None:
        # HACS installs the zip attached to the release, so that is what is read.
        tag = (entry.get("release") or {}).get("tag")
        if not tag or not asset:
            return {"ref": ref, "key": key, "error": "no release asset to read"}
        url = RELEASE_ASSET.format(repo=entry["repo"], tag=urllib.parse.quote(tag), filename=urllib.parse.quote(asset))
        data = gh.download(url, TARBALL_LIMIT)
        if data is None:
            return {"ref": ref, "error": "release asset not downloadable or larger than 30 MB"}
        unpack = scan.zip_python_files
    else:
        data = gh.download(TARBALL.format(repo=entry["repo"], ref=ref), TARBALL_LIMIT)
        if data is None:
            return {"ref": ref, "error": "source not downloadable or larger than 30 MB"}

        def unpack(raw: bytes) -> tuple[dict[str, str], int]:
            return scan.python_files(raw, entry.get("path", ""))

    try:
        files, skipped = unpack(data)
    except Exception as err:
        return {"ref": ref, "error": f"unreadable archive: {type(err).__name__}"}
    if not files:
        return {"ref": ref, "key": key, "error": "no Python files found", "skipped": skipped}
    flags = scan.scan_source(files) + scan.scan_requirements(manifest)
    result = {"ref": ref, "key": key, "files": len(files),
              "lines": sum(t.count("\n") + 1 for t in files.values()), "flags": flags}
    if asset is not None:
        result["asset"] = asset
    if skipped:
        result["skipped"] = skipped
    return result


def _safe_scan(
    gh: GitHub, entry: dict[str, Any], manifest: dict[str, Any] | None, until: float | None = None
) -> dict[str, Any] | None:
    """One repository's scan; a failure stays that repository's, and the night goes on.

    None once the time for scanning is up: the entry goes out unscanned, and
    the next night scans it.
    """
    if until is not None and time.monotonic() >= until:
        return None
    try:
        return scan_entry(gh, entry, manifest)
    except Exception as err:
        _LOGGER.warning("scan of %s failed: %s", entry["repo"], err)
        return {"ref": _scan_ref(entry), "error": f"scan failed: {type(err).__name__}"}


def collect(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any]]:
    """The catalog for the website and the panel, and the scan cache for the next night."""
    start = time.monotonic()

    def by(share: float) -> float | None:
        """When a part of the night has to be done: a share of --budget from the start."""
        return start + share * args.budget * 60 if args.budget else None

    gh = GitHub(find_token())
    default = load_default(gh)
    hacs_names, hacs_domains = load_hacs_data(gh)
    default.update(dict.fromkeys(hacs_names, "hacs"))
    removed = load_removed(gh)
    pending = load_pending(gh)
    brands, core_domains = _brand_domains(gh)
    _LOGGER.info("%d in the default lists, %d removed", len(default), len(removed))

    incomplete: list[str] = []
    candidates: dict[str, str] = {low: name for low, (name, _) in pending.items()}
    if not args.no_search:
        gh.phase(by(0.45))
        try:
            for name in code_search_candidates(gh):
                candidates.setdefault(norm(name), name)
        except GitHubError as err:
            # The queue and what the search found before it stopped still make a catalog.
            _LOGGER.error("code search stopped with %d candidates: %s", len(candidates), err)
            incomplete.append("search")
    denied = load_denylist()
    names = [
        n for low, n in candidates.items() if low not in default and low not in removed and low not in denied
    ]
    # The queue first, so a --limit run still shows what waits for HACS.
    names.sort(key=lambda n: (norm(n) not in pending, n.lower()))
    if args.limit:
        names = names[: args.limit]
    _LOGGER.info("%d candidates to look at", len(names))

    gh.phase(by(0.7))
    meta = fetch_metadata(gh, names)
    if gh.stopped:
        _LOGGER.error("out of time for metadata: %d of %d repositories", len(meta), len(names))
        incomplete.append("metadata")
    gh.phase(by(0.8))

    chosen: dict[str, tuple[dict[str, Any], dict[str, Any], Pending | None]] = {}
    skipped: dict[str, int] = {}

    def skip(reason: str) -> None:
        skipped[reason] = skipped.get(reason, 0) + 1

    for requested, repo in meta.items():
        canonical = repo["nameWithOwner"]
        low = norm(canonical)
        if low in default or low in removed:
            skip("in HACS or removed by HACS")
            continue
        if low in denied:
            skip("on the denylist")
            continue
        if repo.get("isPrivate") or repo.get("isDisabled") or repo.get("isEmpty"):
            skip("private, disabled or empty")
            continue
        if repo.get("isArchived"):
            skip("archived")
            continue
        entry_pending = (pending.get(norm(requested)) or pending.get(low) or (None, None))[1]
        if repo.get("isFork") and not entry_pending:
            skip("fork")
            continue
        kind = analyze.classify(repo, entry_pending.category if entry_pending else None)
        if not kind:
            skip("nothing HACS installs")
            continue
        if kind.get("domain") == "integration_blueprint":
            skip("the integration_blueprint template, unchanged")
            continue
        if low in chosen:
            continue
        chosen[low] = (repo, kind, entry_pending)

    manifest_paths = {
        repo["nameWithOwner"]: (f"{kind['path']}/manifest.json" if kind.get("path") else "manifest.json")
        for repo, kind, _ in chosen.values() if kind["category"] == "integration"
    }
    manifests = {k: _manifest(v) for k, v in fetch_manifests(gh, manifest_paths).items()}
    if gh.stopped:
        _LOGGER.error("out of time for manifests: %d of %d", len(manifests), len(manifest_paths))
        incomplete.append("manifests")
    gh.phase(None)

    entries = []
    for repo, kind, entry_pending in chosen.values():
        manifest = manifests.get(repo["nameWithOwner"])
        if kind["category"] == "integration" and not kind.get("domain") and not manifest:
            skip("integration without a readable manifest")
            continue
        entries.append(build_entry(repo, kind, entry_pending, manifest, brands))

    previous = _load_json(args.previous) or {}
    cache = previous.get("scans", {}) if previous.get("schema") == SCHEMA else {}
    to_scan = []
    for entry in entries:
        if entry["category"] != "integration" or args.no_scan:
            continue
        old = cache.get(norm(entry["repo"]))
        key = scan_key(entry, manifests.get(entry["repo"]))
        if old and key and old.get("key") == key:
            entry["scan"] = old
        else:
            to_scan.append(entry)
    _LOGGER.info("scanning %d integrations (%d from the cache)",
                 len(to_scan), sum(1 for e in entries if "scan" in e))
    unscanned = 0
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {
            pool.submit(_safe_scan, gh, e, manifests.get(e["repo"]), by(1.0)): e for e in to_scan
        }
        for n, (future, entry) in enumerate(futures.items(), 1):
            if (result := future.result()) is None:
                unscanned += 1
            else:
                entry["scan"] = result
            if n % 250 == 0:
                _LOGGER.info("scanned %d of %d", n, len(to_scan))
    if unscanned:
        _LOGGER.error("out of time for scanning: %d integrations go out unscanned", unscanned)
        incomplete.append("scan")

    mark_conflicts(entries, hacs_domains, core_domains)
    for entry in entries:
        entry["score"] = analyze.score(entry)
    entries.sort(key=lambda e: (-e["score"], e["repo"].lower()))
    scans = {norm(e["repo"]): e["scan"] for e in entries if e.get("scan") and e["scan"].get("key")}
    entries = [for_clients(e) for e in entries]

    counts: dict[str, int] = {"total": len(entries), "pending": sum(1 for e in entries if e.get("pending"))}
    for entry in entries:
        counts[entry["category"]] = counts.get(entry["category"], 0) + 1
    _LOGGER.info("catalog: %s; skipped: %s", counts, skipped)
    generated = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    catalog = {
        "schema": SCHEMA,
        "generated": generated,
        "counts": counts,
        "skipped": skipped,
        "repositories": entries,
    }
    if incomplete:
        catalog["incomplete"] = incomplete
    return catalog, {"schema": SCHEMA, "generated": generated, "scans": scans}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", default="site/catalog.json")
    parser.add_argument("--previous", help="last night's scan-cache.json, path or URL")
    parser.add_argument("--cache-out", help="where the scan cache goes; next to --out by default")
    parser.add_argument("--limit", type=int, help="look at only this many candidates (queue first)")
    parser.add_argument("--no-search", action="store_true", help="only the HACS queue, no code search")
    parser.add_argument("--no-scan", action="store_true", help="skip downloading and scanning source")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument(
        "--budget", type=float, metavar="MINUTES",
        help="finish within this many minutes, publishing what there is when GitHub is slow",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S", stream=sys.stderr,
    )
    catalog, cache = collect(args)
    out = Path(args.out)
    for path, data in ((out, catalog), (Path(args.cache_out) if args.cache_out else out.with_name(CACHE_NAME), cache)):
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")))
        tmp.replace(path)
        _LOGGER.info("wrote %s (%d bytes)", path, path.stat().st_size)
    return 0


if __name__ == "__main__":
    sys.exit(main())
