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
MAX_CONDITION_DEPTH = 8
MAX_CONDITION_NODES = 64
MAX_CONDITION_CHILDREN = 16
MAX_DEX_CLASS_QUERIES = 16
MAX_STRING_VALUES = 16
MAX_METHOD_REFERENCES = 16
MAX_METHOD_PARAMETERS = 16
MAX_FACETS = 8
MAX_FACET_TITLE_LENGTH = 40
DEX_CLASS_PATTERN = re.compile(r"L[A-Za-z0-9_$/-]{1,158};?")
DEX_CLASS_DESCRIPTOR = re.compile(r"L[A-Za-z0-9_$/-]{1,158};")
DEX_METHOD_NAME = re.compile(r"[A-Za-z0-9_$<>-]{1,80}")
DEX_PARAMETER_TYPE = re.compile(r"\[*[ZBSCIJFD]|\[*L[A-Za-z0-9_$/-]{1,158};")
MANIFEST_ACTION = re.compile(r"[A-Za-z0-9_.-]{1,160}")
FACET_ID = re.compile(r"[a-z][a-z0-9]*(?:[.-][a-z0-9]+)*")
LOCALE_TAG = re.compile(r"[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*")
REQUIRED_LOCALES = {"en", "zh-Hans"}
FORBIDDEN_LOCALES = {"zh", "zh-CN"}
RELEASE_CHANNELS = {"stable", "preview-only"}
BUILD_CHANNELS = {"preview", "stable"}


def read_rules(chart_dir: Path, channel: str = "preview") -> list[dict]:
    if channel not in BUILD_CHANNELS:
        raise ValueError(f"Unsupported chart release channel: {channel}")
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
        release_channel = rule.get("releaseChannel", "stable")
        if release_channel not in RELEASE_CHANNELS:
            raise ValueError(f"Invalid release channel for {rule_id}: {release_channel}")
        validate_translated_text(rule.get("title"), rule_id, "title", 80)
        validate_calculation(rule, rule_id)
        icon_path = validate_relative_icon_path(rule, rule_id)
        validate_svg(chart_dir / icon_path)
        ids.add(rule_id)
        rule.pop("releaseChannel", None)
        if channel == "preview" or release_channel == "stable":
            rules.append(rule)
    if not rules:
        raise ValueError("At least one chart rule is required")
    if len(rules) > MAX_RULES:
        raise ValueError(f"Chart bundle exceeds {MAX_RULES} rules")
    return sorted(rules, key=lambda item: item["id"])


def validate_calculation(rule: dict, rule_id: str) -> None:
    calculation = rule.get("calculation", {})
    kind = calculation.get("kind")
    if kind == "facets":
        validate_facets(calculation, rule_id)
        return
    if kind != "predicate":
        raise ValueError(f"External rule has an unsupported calculation: {rule_id}")
    predicate = calculation.get("predicate", {})
    if set(calculation) != {"kind", "predicate"}:
        raise ValueError(f"Predicate calculation has unexpected fields: {rule_id}")
    validate_translated_text(predicate.get("matchedTitle"), rule_id, "matchedTitle", 80)
    validate_translated_text(predicate.get("unmatchedTitle"), rule_id, "unmatchedTitle", 80)
    legacy_keys = {"evidence", "operator", "value"}
    legacy_count = sum(key in predicate for key in legacy_keys)
    condition = predicate.get("condition")
    if condition is not None and legacy_count == 0:
        root = condition
    elif condition is None and legacy_count == len(legacy_keys):
        root = {key: predicate[key] for key in legacy_keys}
    else:
        raise ValueError(f"Predicate must define one complete condition: {rule_id}")
    validate_condition(root, rule_id, depth=1, state={"nodes": 0})


def validate_facets(calculation: dict, rule_id: str) -> None:
    if set(calculation) != {"kind", "facets"}:
        raise ValueError(f"Facets calculation has unexpected fields: {rule_id}")
    facets = calculation.get("facets")
    if not isinstance(facets, dict) or set(facets) != {
        "matchedTitle",
        "unmatchedTitle",
        "items",
    }:
        raise ValueError(f"Facets calculation is incomplete: {rule_id}")
    validate_translated_text(facets["matchedTitle"], rule_id, "matchedTitle", 80)
    validate_translated_text(facets["unmatchedTitle"], rule_id, "unmatchedTitle", 80)
    items = facets["items"]
    if not isinstance(items, list) or not 1 <= len(items) <= MAX_FACETS:
        raise ValueError(f"Facets calculation has an invalid item count: {rule_id}")
    facet_ids = set()
    condition_state = {"nodes": 0}
    for facet in items:
        if not isinstance(facet, dict) or set(facet) != {"id", "title", "condition"}:
            raise ValueError(f"Facet has invalid fields: {rule_id}")
        facet_id = facet["id"]
        if not isinstance(facet_id, str) or FACET_ID.fullmatch(facet_id) is None:
            raise ValueError(f"Facet has an invalid id: {rule_id}: {facet_id}")
        if facet_id in facet_ids:
            raise ValueError(f"Facet id is duplicated: {rule_id}: {facet_id}")
        facet_ids.add(facet_id)
        validate_translated_text(
            facet["title"], rule_id, f"facet {facet_id} title", MAX_FACET_TITLE_LENGTH
        )
        validate_condition(facet["condition"], rule_id, depth=1, state=condition_state)


def validate_translated_text(
    text: object, rule_id: str, field_name: str, maximum_length: int
) -> None:
    if not isinstance(text, dict) or set(text) != {"translations"}:
        raise ValueError(f"Rule has an invalid translated {field_name}: {rule_id}")
    translations = text["translations"]
    if (
        not isinstance(translations, dict)
        or not REQUIRED_LOCALES <= set(translations)
        or FORBIDDEN_LOCALES & set(translations)
        or not 2 <= len(translations) <= 16
        or any(
            not isinstance(locale, str)
            or LOCALE_TAG.fullmatch(locale) is None
            or not isinstance(value, str)
            or not 1 <= len(value) <= maximum_length
            for locale, value in translations.items()
        )
    ):
        raise ValueError(f"Rule has an invalid translated {field_name}: {rule_id}")


def validate_condition(condition: dict, rule_id: str, depth: int, state: dict) -> None:
    if not isinstance(condition, dict):
        raise ValueError(f"Predicate condition must be an object: {rule_id}")
    state["nodes"] += 1
    if depth > MAX_CONDITION_DEPTH:
        raise ValueError(f"Predicate condition exceeds maximum depth: {rule_id}")
    if state["nodes"] > MAX_CONDITION_NODES:
        raise ValueError(f"Predicate condition has too many nodes: {rule_id}")

    leaf_keys = {"evidence", "operator", "value"}
    has_leaf = bool(leaf_keys & set(condition))
    logical_keys = [key for key in ("all", "any", "not") if key in condition]
    if int(has_leaf) + len(logical_keys) != 1:
        raise ValueError(f"Predicate condition must define one operation: {rule_id}")
    if has_leaf:
        if set(condition) != leaf_keys:
            raise ValueError(f"Predicate evidence condition is incomplete: {rule_id}")
        validate_evidence(
            condition["evidence"], condition["operator"], condition["value"], rule_id
        )
        return

    logical_key = logical_keys[0]
    if set(condition) != {logical_key}:
        raise ValueError(f"Predicate logical condition has unexpected fields: {rule_id}")
    children = condition[logical_key]
    if logical_key == "not":
        validate_condition(children, rule_id, depth + 1, state)
        return
    if (
        not isinstance(children, list)
        or not 1 <= len(children) <= MAX_CONDITION_CHILDREN
    ):
        raise ValueError(f"Predicate logical condition has invalid children: {rule_id}")
    for child in children:
        validate_condition(child, rule_id, depth + 1, state)


def validate_evidence(evidence: str, operator: str, value: dict, rule_id: str) -> None:
    if not isinstance(value, dict):
        raise ValueError(f"Predicate value must be an object: {rule_id}")
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
    elif evidence == "dex_class":
        queries = value.get("dexClasses")
        if operator != "contains_any":
            raise ValueError(f"DEX class rule must use contains_any: {rule_id}")
        if set(value) != {"dexClasses"} or not isinstance(queries, list) or not (
            1 <= len(queries) <= MAX_DEX_CLASS_QUERIES
        ):
            raise ValueError(f"DEX class rule requires safe class queries: {rule_id}")
        for query in queries:
            validate_dex_class_query(query, rule_id)
    elif evidence == "manifest_receiver_action":
        actions = value.get("strings")
        if operator != "contains_any":
            raise ValueError(f"Manifest receiver action rule must use contains_any: {rule_id}")
        if set(value) != {"strings"} or not safe_string_list(
            actions, MANIFEST_ACTION, MAX_STRING_VALUES
        ):
            raise ValueError(f"Manifest receiver action rule requires safe actions: {rule_id}")
    else:
        raise ValueError(f"Unsupported rule evidence: {rule_id}: {evidence}")


def validate_dex_class_query(query: dict, rule_id: str) -> None:
    allowed_keys = {"name", "stringConstants", "methodReferences"}
    if not isinstance(query, dict) or not query or not set(query) <= allowed_keys:
        raise ValueError(f"DEX class query has invalid fields: {rule_id}")

    name = query.get("name")
    if name is not None:
        if not isinstance(name, dict) or set(name) != {"operator", "value"}:
            raise ValueError(f"DEX class query has an invalid name: {rule_id}")
        operator = name.get("operator")
        pattern = name.get("value")
        if (
            operator not in {"equal", "starts_with"}
            or not isinstance(pattern, str)
            or DEX_CLASS_PATTERN.fullmatch(pattern) is None
            or (operator == "equal" and not pattern.endswith(";"))
        ):
            raise ValueError(f"DEX class query has an invalid name: {rule_id}")

    if "stringConstants" in query and not safe_string_list(
        query["stringConstants"], None, MAX_STRING_VALUES
    ):
        raise ValueError(f"DEX class query has invalid string constants: {rule_id}")

    references = query.get("methodReferences")
    if references is not None:
        if not isinstance(references, list) or not (
            1 <= len(references) <= MAX_METHOD_REFERENCES
        ):
            raise ValueError(f"DEX class query has invalid method references: {rule_id}")
        for reference in references:
            validate_method_reference(reference, rule_id)


def validate_method_reference(reference: dict, rule_id: str) -> None:
    allowed_keys = {"definingClass", "name", "parameterTypes"}
    if (
        not isinstance(reference, dict)
        or not {"definingClass", "name"} <= set(reference)
        or not set(reference) <= allowed_keys
        or not isinstance(reference["definingClass"], str)
        or DEX_CLASS_DESCRIPTOR.fullmatch(reference["definingClass"]) is None
        or not isinstance(reference["name"], str)
        or DEX_METHOD_NAME.fullmatch(reference["name"]) is None
    ):
        raise ValueError(f"DEX class query has an invalid method reference: {rule_id}")
    parameters = reference.get("parameterTypes")
    if parameters is not None and (
        not isinstance(parameters, list)
        or len(parameters) > MAX_METHOD_PARAMETERS
        or any(
            not isinstance(parameter, str)
            or DEX_PARAMETER_TYPE.fullmatch(parameter) is None
            for parameter in parameters
        )
    ):
        raise ValueError(f"DEX class query has invalid method parameters: {rule_id}")


def safe_string_list(values: object, pattern: re.Pattern | None, maximum: int) -> bool:
    return (
        isinstance(values, list)
        and 1 <= len(values) <= maximum
        and all(
            isinstance(value, str)
            and 1 <= len(value) <= 160
            and all(ord(character) >= 32 and ord(character) != 127 for character in value)
            and (pattern is None or pattern.fullmatch(value) is not None)
            for value in values
        )
    )


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
    if "<svg" not in svg or re.search(
        r"viewbox\s*=\s*['\"]0\s+0\s+1024\s+1024['\"]", svg
    ) is None:
        raise ValueError(f"SVG must use a 0 0 1024 1024 viewBox: {path}")


def zip_entry(name: str, data: bytes) -> tuple[zipfile.ZipInfo, bytes]:
    info = zipfile.ZipInfo(name, FIXED_ZIP_TIME)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o100644 << 16
    return info, data


def build_bundle(
    chart_dir: Path,
    output_dir: Path,
    bundle_version: int,
    channel: str = "preview",
    minimum_app_version_code: int = 0,
) -> dict:
    rules = read_rules(chart_dir, channel=channel)
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
        "minimumAppVersionCode": minimum_app_version_code,
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=4, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Build LibChecker chart rules")
    parser.add_argument("--bundle-version", type=int, required=True)
    parser.add_argument("--channel", choices=sorted(BUILD_CHANNELS), default="preview")
    parser.add_argument("--minimum-app-version-code", type=int, default=0)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    if args.bundle_version < 1:
        parser.error("--bundle-version must be positive")
    if args.minimum_app_version_code < 0:
        parser.error("--minimum-app-version-code cannot be negative")

    chart_dir = Path(__file__).resolve().parents[1]
    output_dir = args.output_dir or chart_dir / "cloud" / "v1"
    manifest = build_bundle(
        chart_dir,
        output_dir,
        args.bundle_version,
        channel=args.channel,
        minimum_app_version_code=args.minimum_app_version_code,
    )
    print(
        f"Built chart bundle v{manifest['bundleVersion']} "
        f"({manifest['bundleSize']} bytes, {manifest['bundleSha256']})"
    )


if __name__ == "__main__":
    main()
