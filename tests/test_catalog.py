"""The nightly job's pieces, without the network."""

from __future__ import annotations

import io
import json
import tarfile

from catalog import analyze, scan
from catalog.collect import for_clients
from catalog.sources import repo_from_title, summarize_checks


def _repo(**over):
    repo = {
        "nameWithOwner": "someone/ha-thing",
        "description": "A thing",
        "stargazerCount": 5,
        "isArchived": False,
        "hasIssuesEnabled": True,
        "licenseInfo": {"spdxId": "MIT"},
        "repositoryTopics": {"nodes": [{"topic": {"name": "home-assistant"}}]},
        "hacs": {"text": json.dumps({"name": "Thing", "homeassistant": "2025.1.0"})},
        "root": {"entries": [{"name": "README.md", "type": "blob"}, {"name": "custom_components", "type": "tree"}]},
        "cc": {"entries": [{"name": "thing", "type": "tree", "object": {"entries": [
            {"name": "manifest.json", "type": "blob"}, {"name": "brand", "type": "tree"},
        ]}}]},
    }
    repo.update(over)
    return repo


MANIFEST = {
    "domain": "thing", "name": "Thing", "codeowners": ["@someone"], "version": "1.0.0",
    "documentation": "https://example.com", "issue_tracker": "https://example.com/issues",
}


def test_titles():
    assert repo_from_title("Adds new integration [beolink/HA-CTC-Local-Easyconf]") == "beolink/HA-CTC-Local-Easyconf"
    assert repo_from_title("Added New Integration [ 'rhshorav/hass-peekesp' ]to integration list") == "rhshorav/hass-peekesp"
    assert repo_from_title("Add davecpearce/hacs_smartcocoon") == "davecpearce/hacs_smartcocoon"
    assert repo_from_title("Add 'sim0nx/hass_meteolux' to integration list") == "sim0nx/hass_meteolux"
    assert repo_from_title("Add Verizon 5G Home Gateway integration") is None
    assert repo_from_title("Rename a/b to c/d") is None
    assert repo_from_title("Add owner/repo. Thanks") == "owner/repo"


def test_checks_keep_the_newest_run_per_name():
    contexts = [
        {"__typename": "CheckRun", "name": "Hassfest", "status": "COMPLETED", "conclusion": "CANCELLED", "startedAt": "1"},
        {"__typename": "CheckRun", "name": "Hassfest", "status": "COMPLETED", "conclusion": "SUCCESS", "startedAt": "2"},
        {"__typename": "CheckRun", "name": "Action checks completed", "status": "COMPLETED", "conclusion": "FAILURE", "startedAt": "1"},
        {"__typename": "CheckRun", "name": "HACS action", "status": "COMPLETED", "conclusion": "SUCCESS", "startedAt": "2"},
    ]
    assert summarize_checks(contexts) == ("success", [])
    contexts.append({"__typename": "CheckRun", "name": "Owner", "status": "COMPLETED", "conclusion": "FAILURE", "startedAt": "3"})
    assert summarize_checks(contexts) == ("failure", ["Owner"])
    contexts.append({"__typename": "CheckRun", "name": "Releases", "status": "IN_PROGRESS", "conclusion": None, "startedAt": "4"})
    assert summarize_checks(contexts)[0] == "failure"
    # A cancelled latest run is not a pass, and a queued re-run is newer than any finished one.
    cancelled = [{"__typename": "CheckRun", "name": "HACS action", "status": "COMPLETED", "conclusion": "CANCELLED", "startedAt": "5"}]
    assert summarize_checks(cancelled) == ("pending", [])
    rerun = [
        {"__typename": "CheckRun", "name": "Owner", "status": "COMPLETED", "conclusion": "FAILURE", "startedAt": "5"},
        {"__typename": "CheckRun", "name": "Owner", "status": "QUEUED", "conclusion": None, "startedAt": None},
    ]
    assert summarize_checks(rerun) == ("pending", [])
    assert summarize_checks([]) == (None, [])


def test_classify_integration_and_others():
    kind = analyze.classify(_repo())
    assert kind["category"] == "integration"
    assert kind["domain"] == "thing"
    assert kind["path"] == "custom_components/thing"
    assert kind["brand"] is True

    card = _repo(cc=None, hacs={"text": '{"name": "Card", "filename": "thing-card.js"}'},
                 root={"entries": [{"name": "dist", "type": "tree"}]})
    assert analyze.classify(card)["category"] == "plugin"
    theme = _repo(cc=None, root={"entries": [{"name": "themes", "type": "tree"}]})
    assert analyze.classify(theme)["category"] == "theme"
    nothing = _repo(cc=None, root={"entries": [{"name": "README.md", "type": "blob"}]})
    assert analyze.classify(nothing) is None
    # The queue's own category wins over a guess.
    assert analyze.classify(nothing, hint="plugin")["category"] == "plugin"


def test_checks_follow_hacs():
    repo = _repo()
    kind = analyze.classify(repo)
    checks = analyze.run_checks(repo, kind, MANIFEST, set())
    assert all(checks.values()), checks

    bad = _repo(
        description=None, repositoryTopics={"nodes": []}, hasIssuesEnabled=False,
        licenseInfo={"spdxId": "NOASSERTION"},
        hacs={"text": json.dumps({"name": "Thing", "domains": ["sensor"]})},
        cc={"entries": [{"name": "thing", "type": "tree", "object": {"entries": [{"name": "manifest.json", "type": "blob"}]}}]},
    )
    kind = analyze.classify(bad)
    checks = analyze.run_checks(bad, kind, {**MANIFEST, "issue_tracker": ""}, set())
    assert {k for k, v in checks.items() if v is False} == {
        "description", "topics", "issues", "license", "hacsjson", "integration_manifest", "brands",
    }
    # The brands list stands in for a missing brand folder.
    assert analyze.run_checks(bad, kind, MANIFEST, {"thing"})["brands"] is True
    # A licence outside the known list is not known rather than failed.
    assert analyze.run_checks(_repo(licenseInfo={"spdxId": "Vim"}), kind, MANIFEST, set())["license"] is None


def test_scan_finds_signals_and_skips_comments():
    files = {
        "custom_components/thing/__init__.py": "\n".join([
            "import subprocess",
            "# eval(this is a comment)",
            "value = ast.literal_eval(text)",
            "obj.eval(x)",
            "exec(base64.b64decode(blob))",
            "open('/config/.storage/auth')",
        ]),
        "custom_components/thing/util.py": "mod = importlib.import_module(name)\n",
    }
    flags = {f["rule"]: f for f in scan.scan_source(files)}
    assert flags["dynamic-code"]["where"] == ["custom_components/thing/__init__.py:5"]
    assert flags["obfuscated-exec"]["severity"] == "high"
    assert flags["ha-credentials"]["severity"] == "high"
    assert flags["shell"]["where"] == ["custom_components/thing/__init__.py:1"]
    assert flags["dynamic-import"]["severity"] == "low"
    assert scan.scan_source({"a.py": "import asyncio\nprint('hello')\n"}) == []


def test_scan_requirements():
    flags = scan.scan_requirements({"requirements": ["aiohttp>=3", "git+https://github.com/x/y.git"]})
    assert flags[0]["rule"] == "requirement-url"
    assert scan.scan_requirements({"requirements": ["aiohttp>=3"]}) == []


def test_python_files_reads_only_the_integration():
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        for name, text in {
            "repo-abc/custom_components/thing/__init__.py": "x = 1\n",
            "repo-abc/custom_components/thing/brand/icon.png": "png",
            "repo-abc/tests/test_thing.py": "exec('no')\n",
            "repo-abc/custom_components/other/__init__.py": "y = 2\n",
        }.items():
            data = text.encode()
            info = tarfile.TarInfo(name)
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
    files, skipped = scan.python_files(buffer.getvalue(), "custom_components/thing")
    assert list(files) == ["custom_components/thing/__init__.py"]
    assert skipped == 0
    # A folder renamed after the release: every custom_components folder is read.
    files, _ = scan.python_files(buffer.getvalue(), "custom_components/renamed")
    assert sorted(files) == ["custom_components/other/__init__.py", "custom_components/thing/__init__.py"]


def test_for_clients_keeps_failures_only():
    entry = {
        "repo": "a/b", "checks": {"description": True, "topics": False, "license": None},
        "branch": "main", "commit": "abc", "requirements": [], "path": "custom_components/b",
        "release": {"tag": "v1", "date": "2026-01-01", "commit": "abc"}, "topics": [],
        "pending": {"pr": 1, "since": "2026-01-01", "checks": "success", "failed": []},
        "description": "",
    }
    out = for_clients(entry)
    assert out == {
        "repo": "a/b", "failed": ["topics"], "unknown": ["license"],
        "release": {"tag": "v1", "date": "2026-01-01"},
        "pending": {"pr": 1, "since": "2026-01-01", "checks": "success"},
    }


def test_score_orders_sensibly():
    good = {"stars": 200, "release": {"tag": "v1"}, "checks": {"a": True},
            "updated": "2026-10-20T00:00:00Z", "pending": {"checks": "success"}}
    flagged = {**good, "scan": {"flags": [{"severity": "high"}, {"severity": "high"}]}}
    stale = {"stars": 0, "release": None, "checks": {"a": False}, "updated": "2020-01-01T00:00:00Z"}
    assert analyze.score(good) > analyze.score(flagged) > analyze.score(stale)


def test_denylist(tmp_path):
    from catalog.collect import load_denylist

    path = tmp_path / "denylist.json"
    path.write_text('[{"repository": "Some/Thing", "reason": "asked by the author"}, "other/repo"]')
    assert load_denylist(path) == {"some/thing", "other/repo"}
    assert load_denylist(tmp_path / "missing.json") == set()


def test_scan_is_linear_and_reads_only_newline_lines():
    import time

    start = time.monotonic()
    scan.scan_source({"a.py": "\n" * 200_000 + "import os\n" + "compile(" * 20_000})
    assert time.monotonic() - start < 2
    # \x1c ends a line for str.splitlines() but not for Python.
    flags = scan.scan_source({"a.py": 'x = "\x1c#"; exec(payload)\n'})
    assert [f["rule"] for f in flags] == ["dynamic-code"]


def test_python_files_reads_shallow_files_first():
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        names = [f"repo-abc/custom_components/x/__a/decoy{i:03}.py" for i in range(scan.MAX_FILES)]
        names.append("repo-abc/custom_components/x/__init__.py")
        for name in names:
            info = tarfile.TarInfo(name)
            info.size = 1
            archive.addfile(info, io.BytesIO(b"\n"))
    files, skipped = scan.python_files(buffer.getvalue(), "custom_components/x")
    assert "custom_components/x/__init__.py" in files
    assert skipped == 1


def test_scan_key_changes_with_rules_folder_and_requirements():
    from catalog.collect import scan_key

    entry = {"release": {"commit": "abc"}, "path": "custom_components/x"}
    key = scan_key(entry, {"requirements": ["a==1"]})
    assert key != scan_key(entry, {"requirements": ["a==1", "git+https://x/y"]})
    assert key != scan_key({**entry, "path": "custom_components/y"}, {"requirements": ["a==1"]})
    assert key.startswith(f"{scan.SCAN_VERSION}:abc:")
    assert scan_key(entry, None) is None


def test_unknown_brands_list_leaves_the_check_open():
    repo = _repo(cc={"entries": [{"name": "thing", "type": "tree", "object": {"entries": [{"name": "manifest.json", "type": "blob"}]}}]})
    kind = analyze.classify(repo)
    assert analyze.run_checks(repo, kind, MANIFEST, None)["brands"] is None
    assert analyze.run_checks(repo, kind, MANIFEST, set())["brands"] is False


def test_scan_reads_python_not_text():
    files = {
        "custom_components/x/a.py": "\n".join([
            '"""Never copies secrets.yaml or .storage/auth anywhere."""',
            "class Shell:",
            "    async def exec(self, command):",
            "        return await self.run(command)",
            "    def go(self):",
            "        self.exec('ls')",
            "        return 'secrets.yaml'",
        ]),
    }
    assert scan.scan_source(files) == []


def test_scan_finds_the_real_things():
    files = {
        "custom_components/x/a.py": "\n".join([
            "import asyncio, os, sys, zlib",                                                # 1
            "path = os.path.join(hass.config.path('.storage'), 'auth')",                     # 2
            "await asyncio.create_subprocess_exec('ls')",                                    # 3
            "subprocess_args = [sys.executable, '-m', 'pip', 'install', 'x']",               # 4
            "await asyncio.create_subprocess_exec(*[sys.executable, '-m', 'pip', 'install'])",  # 5
            "exec(zlib.decompress(blob))",                                                    # 6
            "eval(expression)",                                                               # 7
            "token = await hass.auth.async_create_refresh_token(user)",                       # 8
            "code = compile(src, 'x', 'exec')",                                               # 9
        ]),
    }
    flags = {f["rule"]: f for f in scan.scan_source(files)}
    assert flags["ha-credentials"]["where"] == ["custom_components/x/a.py:2"]
    assert flags["shell"]["hits"] == 2
    assert flags["runtime-install"]["where"] == ["custom_components/x/a.py:5"]
    assert flags["obfuscated-exec"]["where"] == ["custom_components/x/a.py:6"]
    assert flags["dynamic-code"]["where"] == [
        "custom_components/x/a.py:6", "custom_components/x/a.py:7", "custom_components/x/a.py:9",
    ]
    assert flags["token-minting"]["severity"] == "medium"


def test_unparseable_file_falls_back_to_patterns():
    flags = scan.scan_source({"a.py": "print 'python 2'\nos.system('ls')\n"})
    assert [f["rule"] for f in flags] == ["shell"]


def test_conflicts():
    from catalog.collect import mark_conflicts

    entries = [
        {"repo": "me/copy", "category": "integration", "domain": "ecoflow"},
        {"repo": "you/other-copy", "category": "integration", "domain": "ecoflow"},
        {"repo": "x/hue-plus", "category": "integration", "domain": "hue"},
        {"repo": "y/unique", "category": "integration", "domain": "unique"},
        {"repo": "z/card", "category": "plugin"},
    ]
    mark_conflicts(entries, {"ecoflow": "orig/ecoflow"}, {"hue"})
    assert entries[0]["conflicts"] == {"hacs": "orig/ecoflow", "shared": 1}
    assert entries[2]["conflicts"] == {"core": True}
    assert "conflicts" not in entries[3] and "conflicts" not in entries[4]


def test_client_scan_is_slim():
    out = for_clients({"repo": "a/b", "checks": {}, "scan": {
        "ref": "0123456789abcdef0123", "key": "3:x", "lines": 10, "files": 2, "flags": []}})
    assert out["scan"] == {"ref": "0123456789ab", "files": 2, "flags": []}


def test_zip_python_files():
    import zipfile

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("__init__.py", "import subprocess\n")
        archive.writestr("translations/en.json", "{}")
        archive.writestr("big.py", "x = 1\n" * 200_000)
    files, skipped = scan.zip_python_files(buffer.getvalue())
    assert list(files) == ["__init__.py"]
    assert skipped == 1
    assert [f["rule"] for f in scan.scan_source(files)] == ["shell"]
