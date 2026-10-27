"""A first read of an integration's Python, looking for what deserves a human's second read.

These are signals, not verdicts: plenty of honest integrations start a subprocess
or import a module by name. The catalog shows what was found and where, and leaves
the judgement to the reader. A hit is never a reason to hide a repository.

The code is read as Python, through its syntax tree, so a method that happens to
be called exec, or secrets.yaml named in a docstring, is not mistaken for the real
thing. A file Python cannot parse falls back to plain text patterns.
"""

from __future__ import annotations

import ast
import io
import re
import tarfile
from typing import Any
import zipfile

# Version of the rules below. A cached scan made under other rules is redone.
SCAN_VERSION = 3
MAX_FILE = 1_000_000
MAX_FILES = 400
MAX_TOTAL = 8_000_000

_SEVERITY = {
    "dynamic-code": "high",
    "obfuscated-exec": "high",
    "marshal": "high",
    "ha-credentials": "high",
    "shell": "medium",
    "runtime-install": "medium",
    "token-minting": "medium",
    "encoded-blob": "medium",
    "dynamic-import": "low",
    "native-code": "low",
    "deletes-files": "low",
}
_SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}

_DECODERS = {"b64decode", "b85decode", "a85decode", "b32decode", "decompress", "fromhex", "unhexlify"}
_SHELL_CALLS = {"os.system", "os.popen", "pty.spawn", "os.posix_spawn", "os.posix_spawnp"}
_TOKEN_CALLS = {"async_create_refresh_token", "async_create_access_token", "async_create_system_user"}
_CREDENTIAL_TEXT = re.compile(r"\.storage[/\\](?:auth|onboarding)\b|auth_provider\.homeassistant")
_BLOB_TEXT = re.compile(r"[A-Za-z0-9+/=_-]{400,}")


def _dotted(node: ast.AST) -> str:
    """exec, os.system, self.hass.auth.async_create_refresh_token; ? for what is not a plain name."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return f"{_dotted(node.value)}.{node.attr}"
    return "?"


def _strings(nodes) -> list[str]:
    return [n.value for n in nodes if isinstance(n, ast.Constant) and isinstance(n.value, str)]


def _scan_tree(tree: ast.AST, hit) -> None:
    bare = {id(stmt.value) for stmt in ast.walk(tree) if isinstance(stmt, ast.Expr)}
    for node in ast.walk(tree):
        line = getattr(node, "lineno", 1)
        if isinstance(node, ast.Call):
            name = _dotted(node.func)
            last = name.rsplit(".", 1)[-1]
            args = [*node.args, *(k.value for k in node.keywords)]
            texts = _strings(args)
            if name in ("exec", "eval", "builtins.exec", "builtins.eval") or (
                name in ("compile", "builtins.compile") and "exec" in texts
            ):
                hit("dynamic-code", line)
                calls = (n for a in args for n in ast.walk(a) if isinstance(n, ast.Call))
                if any(_dotted(c.func).rsplit(".", 1)[-1] in (*_DECODERS, "loads") for c in calls):
                    hit("obfuscated-exec", line)
            if name == "marshal.loads":
                hit("marshal", line)
            if (
                name.startswith("subprocess.")
                or name in _SHELL_CALLS
                or name.startswith(("os.exec", "os.spawn"))
                or last in ("create_subprocess_exec", "create_subprocess_shell")
            ):
                hit("shell", line)
            all_texts = _strings(n for a in args for n in ast.walk(a))
            if last in ("install_package", "ensurepip") or name == "pip.main" or (
                "pip" in all_texts and "install" in all_texts
            ):
                hit("runtime-install", line)
            if last in _TOKEN_CALLS:
                hit("token-minting", line)
            if name in ("__import__", "importlib.import_module", "import_module"):
                hit("dynamic-import", line)
            if name == "shutil.rmtree":
                hit("deletes-files", line)
            # os.path.join(hass.config.path(".storage"), "auth") and the like: the
            # file name is this call's own argument, the folder may sit deeper.
            if any(t in ("auth", "onboarding", "auth_provider.homeassistant") for t in texts) and any(
                t.rstrip("/\\").endswith(".storage") for t in all_texts
            ):
                hit("ha-credentials", line)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            modules = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""]
            for module in modules:
                root = module.split(".")[0]
                if root == "subprocess":
                    hit("shell", line)
                elif root in ("ctypes", "cffi"):
                    hit("native-code", line)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in bare:
            if _CREDENTIAL_TEXT.search(node.value):
                hit("ha-credentials", line)
            if len(node.value) >= 400 and _BLOB_TEXT.fullmatch(node.value):
                hit("encoded-blob", line)


# For files Python cannot parse: the text patterns of the first version.
_FALLBACK: list[tuple[str, re.Pattern[str]]] = [
    ("dynamic-code", re.compile(r"(?<![\w.])(?:exec|eval)\s*\(")),
    ("marshal", re.compile(r"\bmarshal\.loads\s*\(")),
    ("ha-credentials", re.compile(r"\.storage['\"/\\, ]+(?:auth|onboarding)\b|auth_provider\.homeassistant")),
    ("shell", re.compile(r"^[ \t]*(?:import|from)[ \t]+subprocess\b|\bos\.(?:system|popen)\s*\(", re.MULTILINE)),
    ("runtime-install", re.compile(r"\bpip\b[^\n]{0,30}\binstall\b|\binstall_package\s*\(")),
    ("token-minting", re.compile(r"\basync_create_(?:refresh|access)_token\s*\(")),
]


def _scan_text(text: str, hit) -> None:
    for number, line in enumerate(text.split("\n"), 1):
        if line.lstrip().startswith("#"):
            continue
        for rule, pattern in _FALLBACK:
            if pattern.search(line):
                hit(rule, number)


def scan_source(files: dict[str, str]) -> list[dict[str, Any]]:
    """Flags for a set of Python files, one per rule, with up to three places each."""
    found: dict[str, dict[str, Any]] = {}

    for path, text in sorted(files.items()):

        def hit(rule: str, line: int, path: str = path) -> None:
            flag = found.setdefault(rule, {"rule": rule, "severity": _SEVERITY[rule], "hits": 0, "where": []})
            flag["hits"] += 1
            if len(flag["where"]) < 3:
                flag["where"].append(f"{path}:{line}")

        try:
            tree = ast.parse(text)
        except (SyntaxError, ValueError, RecursionError, MemoryError):
            _scan_text(text, hit)
            continue
        _scan_tree(tree, hit)
    return sorted(found.values(), key=lambda f: (_SEVERITY_ORDER[f["severity"]], f["rule"]))


def scan_requirements(manifest: dict[str, Any] | None) -> list[dict[str, Any]]:
    flags = []
    requirements = (manifest or {}).get("requirements") or []
    from_url = [r for r in requirements if isinstance(r, str) and ("://" in r or r.startswith("git+"))]
    if from_url:
        flags.append({"rule": "requirement-url", "severity": "medium", "hits": len(from_url),
                      "where": from_url[:3]})
    return flags


def python_files(tarball: bytes, content_path: str) -> tuple[dict[str, str], int]:
    """The .py files under content_path in a GitHub source tarball, and how many were left unread.

    Files are read shallowest first, so padding a deep folder with decoys does not
    push the integration's own modules past the limits. When nothing lies under
    content_path, as when the folder was renamed after the release, every
    custom_components folder is read instead.
    """
    prefix = content_path.strip("/") + "/" if content_path.strip("/") else ""
    with tarfile.open(fileobj=io.BytesIO(tarball), mode="r:gz") as archive:
        members = []
        for member in archive.getmembers():
            if not member.isfile() or not member.name.endswith(".py"):
                continue
            path = member.name.split("/", 1)[1] if "/" in member.name else member.name
            # Tests and tooling never run inside Home Assistant.
            if path.startswith(("tests/", "test/", "scripts/", ".github/")):
                continue
            members.append((path, member))
        chosen = [(p, m) for p, m in members if p.startswith(prefix)] if prefix else members
        if not chosen:
            chosen = [(p, m) for p, m in members if p.startswith("custom_components/")]

        def read(member: tarfile.TarInfo) -> bytes | None:
            handle = archive.extractfile(member)
            return handle.read(MAX_FILE + 1) if handle else None

        return _read_limited([(path, member.size, member) for path, member in chosen], read)


def _read_limited(entries, read) -> tuple[dict[str, str], int]:
    """Shallowest first, within the limits on file size, file count and total size."""
    files: dict[str, str] = {}
    skipped = total = 0
    for path, size, item in sorted(entries, key=lambda e: (e[0].count("/"), e[0])):
        if size > MAX_FILE or len(files) >= MAX_FILES or total + size > MAX_TOTAL:
            skipped += 1
            continue
        data = read(item)
        if data is None:
            skipped += 1
            continue
        files[path] = data[: MAX_FILE + 1].decode("utf-8", errors="replace")
        total += size
    return files, skipped


def zip_python_files(archive_bytes: bytes) -> tuple[dict[str, str], int]:
    """The .py files in a release asset zip, the way HACS unpacks it into the integration's folder."""
    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
        entries = [
            (info.filename, info.file_size, info)
            for info in archive.infolist()
            if not info.is_dir() and info.filename.endswith(".py") and not info.filename.startswith(("/", ".."))
        ]

        def read(info: zipfile.ZipInfo) -> bytes | None:
            # Read no more than the header promised; a lying header ends here, not in memory.
            with archive.open(info) as handle:
                return handle.read(MAX_FILE + 1)

        return _read_limited(entries, read)
