#!/usr/bin/env python3

import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path, PurePosixPath


MAX_RULES = 64
MAX_ICON_BYTES = 64 * 1024
MAX_BUNDLE_BYTES = 2 * 1024 * 1024
FIXED_ZIP_TIME = (1980, 1, 1, 0, 0, 0)
FORBIDDEN_SVG = (
    "<!doctype",
    "<!entity",
    "<?xml-stylesheet",
    "<script",
    "<foreignobject",
    "<image",
    "<style",
    "<text",
    "href=",
    "xlink:",
    "url(",
)


def read_rules(chart_dir: Path) -> list[dict]:
    rules = []
    ids = set()
    for rule_path in sorted((chart_dir / "rules").glob("*.json")):
        rule = json.loads(rule_path.read_text(encoding="utf-8"))
        rule_id = rule.get("id")
        if not isinstance(rule_id, str) or not re.fullmatch(
            r"official\.[a-z0-9]+(?:[.-][a-z0-9]+)*", rule_id
        ):
            raise ValueError(f"Invalid official rule id in {rule_path}: {rule_id}")
        if rule_id in ids:
            raise ValueError(f"Duplicate rule id: {rule_id}")
        if rule.get("source") != "official":
            raise ValueError(f"External rule must use official source: {rule_id}")
        validate_calculation(rule, rule_id)
        icon_path = validate_relative_icon_path(rule, rule_id)
        validate_svg(chart_dir / icon_path)
        ids.add(rule_id)
        rules.append(rule)
    if not rules:
        raise ValueError("At least one chart rule is required")
    if len(rules) > MAX_RULES:
        raise ValueError(f"Chart bundle exceeds {MAX_RULES} rules")
    return sorted(rules, key=lambda item: item["id"])


def validate_calculation(rule: dict, rule_id: str) -> None:
    calculation = rule.get("calculation", {})
    predicate = calculation.get("predicate", {})
    if calculation.get("kind") != "predicate":
        raise ValueError(f"External rule must use a predicate calculation: {rule_id}")
    evidence = predicate.get("evidence")
    operator = predicate.get("operator")
    value = predicate.get("value", {})
    if evidence == "target_sdk":
        if operator not in {"equal", "greater_than_or_equal", "less_than_or_equal"}:
            raise ValueError(f"Target SDK rule has an invalid operator: {rule_id}")
        if set(value) != {"integer"} or not isinstance(value["integer"], int):
            raise ValueError(f"Target SDK rule requires one integer value: {rule_id}")
    elif evidence == "native_library":
        library_name = value.get("string")
        if operator != "contains":
            raise ValueError(f"Native library rule must use contains: {rule_id}")
        if set(value) != {"string"} or not isinstance(library_name, str) or not re.fullmatch(
            r"[A-Za-z0-9._+-]{1,160}", library_name
        ):
            raise ValueError(f"Native library rule requires one safe library name: {rule_id}")
    else:
        raise ValueError(f"Unsupported rule evidence: {rule_id}: {evidence}")


def validate_relative_icon_path(rule: dict, rule_id: str) -> PurePosixPath:
    icon = rule.get("icon", {})
    asset = icon.get("asset")
    if not isinstance(asset, str):
        raise ValueError(f"Rule is missing an SVG asset: {rule_id}")
    icon_path = PurePosixPath(asset)
    if (
        icon_path.is_absolute()
        or ".." in icon_path.parts
        or len(icon_path.parts) != 2
        or icon_path.parts[0] != "icons"
        or icon_path.suffix.lower() != ".svg"
    ):
        raise ValueError(f"Unsafe SVG asset path for {rule_id}: {asset}")
    return icon_path


def validate_svg(path: Path) -> None:
    data = path.read_bytes()
    if len(data) > MAX_ICON_BYTES:
        raise ValueError(f"SVG exceeds {MAX_ICON_BYTES} bytes: {path}")
    svg = data.decode("utf-8").lower()
    forbidden = next((token for token in FORBIDDEN_SVG if token in svg), None)
    if forbidden:
        raise ValueError(f"SVG contains forbidden content {forbidden}: {path}")
    if "<svg" not in svg or "viewbox=" not in svg:
        raise ValueError(f"SVG root or viewBox is missing: {path}")


def zip_entry(name: str, data: bytes) -> tuple[zipfile.ZipInfo, bytes]:
    info = zipfile.ZipInfo(name, FIXED_ZIP_TIME)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o100644 << 16
    return info, data


def build_bundle(chart_dir: Path, output_dir: Path, bundle_version: int) -> dict:
    rules = read_rules(chart_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    catalog = {
        "schemaVersion": 1,
        "definitions": rules,
    }
    catalog_bytes = (
        json.dumps(catalog, ensure_ascii=False, indent=4, sort_keys=True) + "\n"
    ).encode("utf-8")
    entries = [("catalog.json", catalog_bytes)]
    icon_assets = sorted({rule["icon"]["asset"] for rule in rules})
    for asset in icon_assets:
        entries.append((asset, (chart_dir / asset).read_bytes()))

    bundle_path = output_dir / "chart.bundle"
    with zipfile.ZipFile(bundle_path, "w") as archive:
        for name, data in entries:
            info, payload = zip_entry(name, data)
            archive.writestr(info, payload)

    bundle_bytes = bundle_path.read_bytes()
    if len(bundle_bytes) > MAX_BUNDLE_BYTES:
        raise ValueError(f"Chart bundle exceeds {MAX_BUNDLE_BYTES} bytes")
    manifest = {
        "schemaVersion": 1,
        "bundleVersion": bundle_version,
        "bundleSha256": hashlib.sha256(bundle_bytes).hexdigest(),
        "bundleSize": len(bundle_bytes),
        "minimumAppVersionCode": 0,
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=4, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Build LibChecker chart rules")
    parser.add_argument("--bundle-version", type=int, required=True)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    if args.bundle_version < 1:
        parser.error("--bundle-version must be positive")

    chart_dir = Path(__file__).resolve().parents[1]
    output_dir = args.output_dir or chart_dir / "cloud" / "v1"
    manifest = build_bundle(chart_dir, output_dir, args.bundle_version)
    print(
        f"Built chart bundle v{manifest['bundleVersion']} "
        f"({manifest['bundleSize']} bytes, {manifest['bundleSha256']})"
    )


if __name__ == "__main__":
    main()
