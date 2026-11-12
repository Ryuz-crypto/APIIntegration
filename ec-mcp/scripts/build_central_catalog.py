#!/usr/bin/env python3
"""Build the Aruba Central v2 catalog from the official Postman collections.

Usage:
    python scripts/build_central_catalog.py "MRT APIs.postman_collection.json" \
        "Configuration APIs.postman_collection.json" --output ec_mcp/catalogs/central-v2.json

The output catalog is compact: operation id, name, method, path (with
{param} placeholders), group, path parameters, query parameter examples
and small body examples only. The huge Postman response examples are
intentionally dropped.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from collections import Counter
from pathlib import Path


def clean_path(raw: str) -> str:
    raw = raw.split("?")[0].replace("{{baseUrl}}", "")
    return re.sub(r":([a-zA-Z0-9_-]+)", r"{\1}", raw)


def slug(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "_", name.strip()).strip("_").lower() or "op"


def extract(collection: dict) -> list[dict]:
    operations: list[dict] = []
    seen: set[tuple[str, str]] = set()

    def walk(items: list, group: str) -> None:
        for item in items:
            if "item" in item:
                walk(item["item"], (group + "/" + item["name"]).strip("/"))
                continue
            request = item.get("request", {})
            url = request.get("url", {})
            raw = url.get("raw", "") if isinstance(url, dict) else str(url)
            if not raw:
                continue
            path = clean_path(raw)
            if not path.startswith("/"):
                continue
            method = str(request.get("method", "GET")).upper()
            key = (method, path)
            if key in seen:
                continue
            seen.add(key)
            query = []
            if isinstance(url, dict):
                for param in url.get("query", []) or []:
                    if isinstance(param, dict) and param.get("key"):
                        query.append({"key": str(param["key"]), "example": str(param.get("value", ""))[:120]})
            body = None
            body_spec = request.get("body", {})
            if isinstance(body_spec, dict) and body_spec.get("mode") == "raw":
                try:
                    parsed = json.loads(body_spec.get("raw", ""))
                    body = parsed if len(json.dumps(parsed)) < 2000 else None
                except json.JSONDecodeError:
                    body = None
            operations.append(
                {
                    "id": f"{method.lower()}_{slug(item.get('name', ''))}",
                    "name": str(item.get("name", ""))[:120],
                    "method": method,
                    "path": path,
                    "group": group,
                    "path_params": re.findall(r"\{([a-zA-Z0-9_-]+)\}", path),
                    "query": query[:12],
                    "body_example": body,
                }
            )

    walk(collection.get("item", []), "")
    used: Counter[str] = Counter()
    for operation in operations:
        used[operation["id"]] += 1
        if used[operation["id"]] > 1:
            operation["id"] = f"{operation['id']}_{used[operation['id']]}"
    return operations


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("collections", nargs="+", help="Postman collection JSON files")
    parser.add_argument("--output", default="ec_mcp/catalogs/central-v2.json")
    args = parser.parse_args()

    operations: list[dict] = []
    names: list[str] = []
    for path in args.collections:
        with open(path, encoding="utf-8") as stream:
            document = json.load(stream)
        names.append(str(document.get("info", {}).get("name", Path(path).name)))
        operations.extend(extract(document))

    catalog = {
        "name": "HPE Aruba Networking Central - New Central REST API",
        "version": "v2",
        "source": "Official New Central Postman collections (" + ", ".join(names) + ")",
        "operations": operations,
    }
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as stream:
        json.dump(catalog, stream, ensure_ascii=False, indent=1)
    reads = sum(1 for op in operations if op["method"] == "GET")
    print(
        f"catalog: {len(operations)} operations ({reads} GET, {len(operations) - reads} writes), "
        f"{os.path.getsize(args.output) // 1024} KB -> {args.output}"
    )


if __name__ == "__main__":
    main()
