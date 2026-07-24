import argparse
import json
import re
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[2]
SDK_DETAILS_DIR = ROOT / "sdk-details"
SDKS_DIR = SDK_DETAILS_DIR / "sdks"
CATALOG_PATH = SDK_DETAILS_DIR / "catalog.json"
UUID_PATTERN = re.compile(
    r"^[0-9A-F]{8}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{12}$"
)
SDK_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
SUPPORTED_SOURCE_OPERATORS = {"package_file"}
SUPPORTED_READER_OPERATORS = {"ascii_strings"}
SUPPORTED_CAPTURE_TYPES = {"sha1", "semver_channel"}
MAX_TARGET_UUIDS = 32
MAX_CATALOG_ENTRIES = 128
MAX_FILE_NAME_LENGTH = 128
MAX_ARCHIVE_PATH_LENGTH = 256
MAX_LABELS = 16
MAX_LABEL_LENGTH = 80


def load_json(path):
    with path.open(encoding="utf-8") as source:
        return json.load(source)


def validate_remote_path(value, field):
    if not isinstance(value, str) or not value.startswith("sdk-details/"):
        raise ValueError(f"{field} must stay under sdk-details/: {value!r}")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or "://" in value or "\\" in value:
        raise ValueError(f"Unsafe {field}: {value!r}")


def require_int(value, field, minimum, maximum):
    if not isinstance(value, int) or not minimum <= value <= maximum:
        raise ValueError(f"Invalid {field}: {value!r}")


def validate_definition(path, data):
    if data.get("schema_version") != 1:
        raise ValueError(f"Unsupported schema_version in {path}")
    sdk_id = data.get("sdk_id")
    if not isinstance(sdk_id, str) or not SDK_ID_PATTERN.fullmatch(sdk_id):
        raise ValueError(f"Invalid sdk_id in {path}: {sdk_id!r}")
    if path.parent.name != sdk_id:
        raise ValueError(f"sdk_id must match directory name in {path}")

    target_uuids = data.get("target_uuids")
    if (
        not isinstance(target_uuids, list)
        or not target_uuids
        or len(target_uuids) > MAX_TARGET_UUIDS
    ):
        raise ValueError(f"target_uuids must be a non-empty list in {path}")
    if len(target_uuids) != len(set(target_uuids)):
        raise ValueError(f"Duplicate target UUID in {path}")
    for target_uuid in target_uuids:
        if not isinstance(target_uuid, str) or not UUID_PATTERN.fullmatch(target_uuid):
            raise ValueError(f"Invalid target UUID in {path}: {target_uuid!r}")

    outputs = set()
    probes = data.get("probes")
    if not isinstance(probes, list) or not 1 <= len(probes) <= 8:
        raise ValueError(f"Invalid probes in {path}")
    for probe in probes:
        probe_id = probe.get("id")
        if not isinstance(probe_id, str) or not SDK_ID_PATTERN.fullmatch(probe_id):
            raise ValueError(f"Invalid probe id in {path}")
        source = probe.get("source", {})
        reader = probe.get("reader", {})
        if source.get("operator") not in SUPPORTED_SOURCE_OPERATORS:
            raise ValueError(f"Unsupported source operator in {path}")
        if reader.get("operator") not in SUPPORTED_READER_OPERATORS:
            raise ValueError(f"Unsupported reader operator in {path}")
        file_name = source.get("file_name")
        if (
            not isinstance(file_name, str)
            or not file_name
            or len(file_name) > MAX_FILE_NAME_LENGTH
            or "/" in file_name
            or "\\" in file_name
        ):
            raise ValueError(f"Invalid package file name in {path}")
        archive_paths = source.get("archive_paths")
        if not isinstance(archive_paths, list) or not 1 <= len(archive_paths) <= 16:
            raise ValueError(f"Invalid archive paths in {path}")
        if len(archive_paths) != len(set(archive_paths)):
            raise ValueError(f"Duplicate archive path in {path}")
        for archive_path in archive_paths:
            if (
                not isinstance(archive_path, str)
                or not archive_path
                or len(archive_path) > MAX_ARCHIVE_PATH_LENGTH
                or archive_path.startswith("/")
                or ".." in PurePosixPath(archive_path).parts
                or "\\" in archive_path
            ):
                raise ValueError(f"Unsafe archive path in {path}: {archive_path!r}")
        require_int(reader.get("max_bytes_per_file"), "max_bytes_per_file", 1, 64 * 1024 * 1024)
        require_int(reader.get("max_total_bytes"), "max_total_bytes", 1, 128 * 1024 * 1024)
        captures = probe.get("captures")
        if not isinstance(captures, list) or not 1 <= len(captures) <= 8:
            raise ValueError(f"Invalid captures in {path}")
        for capture in captures:
            output = capture.get("output")
            if not isinstance(output, str) or not SDK_ID_PATTERN.fullmatch(output):
                raise ValueError(f"Invalid capture output in {path}")
            if capture.get("type") not in SUPPORTED_CAPTURE_TYPES:
                raise ValueError(f"Unsupported capture type in {path}")
            require_int(capture.get("max_results"), "max_results", 1, 16)
            outputs.add(output)

    lookups = data.get("lookups", [])
    if not isinstance(lookups, list) or len(lookups) > 8:
        raise ValueError(f"Invalid lookups in {path}")
    for lookup in lookups:
        if lookup.get("input") not in outputs:
            raise ValueError(f"Lookup input is not produced in {path}")
        validate_remote_path(lookup.get("path_template"), "path_template")
        if lookup["path_template"].count("{value}") != 1:
            raise ValueError(f"path_template must contain one {{value}} in {path}")
        require_int(lookup.get("max_requests"), "max_requests", 1, 4)
        require_int(lookup.get("max_items"), "max_items", 1, 50)
        for field_name in ("expected_field", "items_field"):
            field_value = lookup.get(field_name)
            if field_value is not None and (
                not isinstance(field_value, str)
                or not SDK_ID_PATTERN.fullmatch(field_value)
            ):
                raise ValueError(f"Invalid {field_name} in {path}")
        lookup_outputs = lookup.get("outputs")
        if not isinstance(lookup_outputs, list) or not 1 <= len(lookup_outputs) <= 16:
            raise ValueError(f"Invalid lookup outputs in {path}")
        for output_mapping in lookup_outputs:
            output = output_mapping.get("output")
            field = output_mapping.get("field")
            if not isinstance(output, str) or not SDK_ID_PATTERN.fullmatch(output):
                raise ValueError(f"Invalid lookup output in {path}")
            if not isinstance(field, str) or not SDK_ID_PATTERN.fullmatch(field):
                raise ValueError(f"Invalid lookup field in {path}")
            outputs.add(output)

    presentation = data.get("presentation", {})
    summary = presentation.get("summary")
    details = presentation.get("details", [])
    if not isinstance(summary, list) or not 1 <= len(summary) <= 2:
        raise ValueError(f"Presentation summary must contain one or two fields in {path}")
    if not isinstance(details, list) or len(details) > 8:
        raise ValueError(f"Invalid presentation details in {path}")
    for item in summary + details:
        labels = item.get("label")
        if not isinstance(labels, dict) or not isinstance(labels.get("default"), str):
            raise ValueError(f"Presentation label requires a default value in {path}")
        if not 1 <= len(labels) <= MAX_LABELS or any(
            not isinstance(label, str)
            or not label
            or len(label) > MAX_LABEL_LENGTH
            for label in labels.values()
        ):
            raise ValueError(f"Invalid presentation labels in {path}")
        if item.get("source") not in outputs:
            raise ValueError(f"Presentation source is not produced in {path}")
        require_int(item.get("max_values"), "max_values", 1, 8)

    return sdk_id, target_uuids


def collect_rule_uuids():
    uuids = set()
    for path in ROOT.glob("*-libs/**/*.json"):
        data = load_json(path)
        value = data.get("uuid") if isinstance(data, dict) else None
        if isinstance(value, str):
            uuids.add(value)
    return uuids


def build_catalog():
    rule_uuids = collect_rule_uuids()
    uuid_owners = {}
    entries = []
    for path in sorted(SDKS_DIR.glob("*/definition.json")):
        data = load_json(path)
        sdk_id, target_uuids = validate_definition(path, data)
        for target_uuid in target_uuids:
            if target_uuid not in rule_uuids:
                raise ValueError(f"Unknown rule UUID {target_uuid} in {path}")
            previous = uuid_owners.setdefault(target_uuid, sdk_id)
            if previous != sdk_id:
                raise ValueError(f"Rule UUID {target_uuid} belongs to multiple SDKs")
        relative_path = path.relative_to(ROOT).as_posix()
        validate_remote_path(relative_path, "definition")
        entries.append(
            {
                "sdk_id": sdk_id,
                "library_uuids": sorted(target_uuids),
                "definition": relative_path,
            }
        )
    if not entries:
        raise ValueError("No SDK detail definitions found")
    if len(entries) > MAX_CATALOG_ENTRIES:
        raise ValueError("Too many SDK detail definitions")
    return {"schema_version": 1, "entries": entries}


def serialized_catalog():
    return json.dumps(build_catalog(), ensure_ascii=False, indent=2) + "\n"


def write_catalog():
    content = serialized_catalog()
    if CATALOG_PATH.exists() and CATALOG_PATH.read_text(encoding="utf-8") == content:
        return False
    temporary = CATALOG_PATH.with_suffix(".json.tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(CATALOG_PATH)
    return True


def check_catalog():
    expected = serialized_catalog()
    if not CATALOG_PATH.exists() or CATALOG_PATH.read_text(encoding="utf-8") != expected:
        raise ValueError("sdk-details/catalog.json is stale; run validate.py --write")
    print(f"Validated {len(json.loads(expected)['entries'])} SDK detail definitions")


def main():
    parser = argparse.ArgumentParser(description="Validate SDK detail definitions and catalog")
    parser.add_argument("--write", action="store_true", help="regenerate catalog.json")
    args = parser.parse_args()
    if args.write:
        changed = write_catalog()
        print("Updated SDK details catalog" if changed else "SDK details catalog is current")
    check_catalog()


if __name__ == "__main__":
    main()
