"""Put the website together: the static files, the shared component and a catalog.

    python scripts/build_site.py --catalog site/catalog.json --out public
"""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parent.parent
COMPONENT = ROOT / "custom_components" / "bazaar" / "frontend" / "bazaar-catalog.js"


def build(catalog: Path, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    for path in (ROOT / "site").iterdir():
        if path.is_file() and path.name not in ("catalog.json", "bazaar-catalog.js"):
            shutil.copy2(path, out / path.name)
    shutil.copy2(COMPONENT, out / COMPONENT.name)
    if catalog.resolve() != (out / "catalog.json").resolve():
        shutil.copy2(catalog, out / "catalog.json")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=ROOT / "public")
    args = parser.parse_args()
    build(args.catalog, args.out)
