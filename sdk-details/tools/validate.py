import argparse
import json
import re
from pathlib import Path, PurePosixPath

import generate_androidx_definitions


ROOT = Path(__file__).resolve().parents[2]
SDK_DETAILS_DIR = ROOT / "sdk-details"
SDKS_DIR = SDK_DETAILS_DIR / "sdks"
CATALOG_PATH = SDK_DETAILS_DIR / "catalog.json"
UUID_PATTERN = re.compile(
    r"^[0-9A-F]{8}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{12}$"
)
SDK_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
SUPPORTED_SCHEMA_VERSIONS = {1, 2, 3}
V1_READER_OPERATORS = {"ascii_strings"}
V2_READER_OPERATORS = {"ascii_strings", "file_sha256"}
V1_CAPTURE_TYPES = {"sha1", "semver_channel"}
V2_ASCII_CAPTURE_TYPES = {
    "sha1",
    "semver_channel",
    "semver",
    "prefixed_semver",
}
V2_DIGEST_CAPTURE_TYPES = {"sha256"}
MAX_TARGET_UUIDS = 32
MAX_CATALOG_ENTRIES = 128
MAX_FILE_NAME_LENGTH = 128
MAX_ARCHIVE_PATH_LENGTH = 256
MAX_LABELS = 16
MAX_LABEL_LENGTH = 80
MAX_CAPTURE_PREFIX_LENGTH = 80
FILE_PROVIDER_UUID = "7B1DA564-ADCF-437B-891E-203CBFF847BE"


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
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError(f"Invalid {field}: {value!r}")


def validate_archive_entry(value, path):
    if (
        not isinstance(value, str)
        or not 1 <= len(value) <= MAX_ARCHIVE_PATH_LENGTH
        or any(part in {"", ".", ".."} for part in value.split("/"))
        or "\\" in value
        or ".." in value
        or any(ord(character) < 32 for character in value)
    ):
        raise ValueError(f"Unsafe archive entry in {path}: {value!r}")


HEADER_LOAD = re.compile(r"(?:u8|u32le|u32be|u64be)@(end|[0-9]{1,3})")
HEADER_FORMAT = re.compile(r"(?:#|\[[A-Za-z]+\]|[A-Za-z0-9._-])+")


def validate_operand(value, path):
    if not isinstance(value, str) or len(value) > 64:
        raise ValueError(f"Invalid header operand in {path}")
    terms = value.split("+")
    if len(terms) > 2:
        raise ValueError(f"Too many operand terms in {path}")
    for term in terms:
        if term in {"end", "size"}:
            continue
        if re.fullmatch(r"[0-9]{1,19}", term) and int(term) <= 2**63 - 1:
            continue
        load = HEADER_LOAD.fullmatch(term)
        if load and (load[1] == "end" or int(load[1]) <= 511):
            continue
        raise ValueError(f"Invalid header operand in {path}: {term!r}")


def validate_header_reader(reader, path):
    layouts = reader.get("layouts")
    if not isinstance(layouts, list) or not 1 <= len(layouts) <= 8:
        raise ValueError(f"Invalid binary header layouts in {path}")
    for layout in layouts:
        if not isinstance(layout, dict) or set(layout) != {"offset", "checks"}:
            raise ValueError(f"Invalid binary header layout in {path}")
        require_int(layout["offset"], "offset", 0, 511)
        checks = layout["checks"]
        if not isinstance(checks, list) or not 1 <= len(checks) <= 24:
            raise ValueError(f"Invalid binary header checks in {path}")
        for check in checks:
            if not isinstance(check, dict) or set(check) != {"left", "op", "right"}:
                raise ValueError(f"Invalid binary header check in {path}")
            if check["op"] not in ("eq", "le", "ge"):
                raise ValueError(f"Unknown comparison in {path}")
            validate_operand(check["left"], path)
            validate_operand(check["right"], path)


def validate_formats(formats, path):
    if not isinstance(formats, list) or len(formats) > 8:
        raise ValueError(f"Invalid format list in {path}")
    for mask in formats:
        if (not isinstance(mask, str) or not 1 <= len(mask) <= 80
                or "##" in mask or not HEADER_FORMAT.fullmatch(mask)):
            raise ValueError(f"Invalid capture format in {path}: {mask!r}")


def validate_native_library_names(names, path):
    if not isinstance(names, list) or not 1 <= len(names) <= 16:
        raise ValueError(f"Invalid native_library_names in {path}")
    for name in names:
        if (not isinstance(name, str) or len(name) > MAX_FILE_NAME_LENGTH
                or ".." in name or not re.fullmatch(r"[A-Za-z0-9_+.-]+\.so", name)):
            raise ValueError(f"Invalid native library basename in {path}: {name!r}")
    if len(set(names)) != len(names):
        raise ValueError(f"Duplicate native library name in {path}")


def validate_definition(path, data):
    schema_version = data.get("schema_version")
    if schema_version not in SUPPORTED_SCHEMA_VERSIONS:
        raise ValueError(f"Unsupported schema_version in {path}")
    if "native_library_names" in data:
        if schema_version != 3:
            raise ValueError(f"native_library_names requires schema 3 in {path}")
        validate_native_library_names(data["native_library_names"], path)
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
    truncated_outputs = set()
    lookup_outputs_by_name = set()
    probes = data.get("probes")
    if not isinstance(probes, list) or not 1 <= len(probes) <= 8:
        raise ValueError(f"Invalid probes in {path}")
    for probe in probes:
        probe_id = probe.get("id")
        if not isinstance(probe_id, str) or not SDK_ID_PATTERN.fullmatch(probe_id):
            raise ValueError(f"Invalid probe id in {path}")
        source = probe.get("source", {})
        reader = probe.get("reader", {})
        reader_operator = reader.get("operator")
        if schema_version == 3 and source.get("operator") == "archive_entry":
            if set(source) - {"operator", "archive_paths", "container"}:
                raise ValueError(f"Unexpected archive source field in {path}")
            if reader_operator != "binary_header":
                raise ValueError(f"Unsupported archive reader in {path}")
            validate_header_reader(reader, path)
            if "container" in source:
                container = source["container"]
                if (not isinstance(container, dict) or set(container) != {"format", "entry"}
                        or container["format"] != "unityfs"):
                    raise ValueError(f"Unsupported archive container in {path}")
                validate_archive_entry(container["entry"], path)
        elif source.get("operator") == "package_file":
            if "container" in source or "layouts" in reader:
                raise ValueError(f"Unexpected binary header fields in package probe in {path}")
            supported_readers = V1_READER_OPERATORS if schema_version == 1 else V2_READER_OPERATORS
            if reader_operator not in supported_readers:
                raise ValueError(f"Unsupported reader or container in {path}")
            file_name = source.get("file_name")
            if (
                not isinstance(file_name, str)
                or not file_name
                or len(file_name) > MAX_FILE_NAME_LENGTH
                or "/" in file_name
                or "\\" in file_name
            ):
                raise ValueError(f"Invalid package file name in {path}")
        else:
            raise ValueError(f"Unsupported source operator in {path}")
        archive_paths = source.get("archive_paths")
        if not isinstance(archive_paths, list) or not 1 <= len(archive_paths) <= 16:
            raise ValueError(f"Invalid archive paths in {path}")
        if len(archive_paths) != len(set(archive_paths)):
            raise ValueError(f"Duplicate archive path in {path}")
        for archive_path in archive_paths:
            if source.get("operator") == "archive_entry":
                validate_archive_entry(archive_path, path)
            elif (
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
            capture_type = capture.get("type")
            if schema_version == 1:
                supported_captures = V1_CAPTURE_TYPES
            elif reader_operator == "binary_header":
                supported_captures = {"ascii_z"}
                validate_formats(capture.get("formats", []), path)
            elif reader_operator == "file_sha256":
                supported_captures = V2_DIGEST_CAPTURE_TYPES
            else:
                supported_captures = V2_ASCII_CAPTURE_TYPES
            if "formats" in capture and capture_type != "ascii_z":
                raise ValueError(f"Unexpected capture formats in {path}")
            if capture_type not in supported_captures:
                raise ValueError(f"Unsupported capture type in {path}")
            prefix = capture.get("prefix")
            if capture_type == "prefixed_semver":
                if (
                    not isinstance(prefix, str)
                    or not prefix
                    or len(prefix) > MAX_CAPTURE_PREFIX_LENGTH
                    or any(not 0x20 <= ord(character) <= 0x7E for character in prefix)
                ):
                    raise ValueError(f"Invalid capture prefix in {path}")
            elif prefix is not None:
                raise ValueError(f"Unexpected capture prefix in {path}")
            require_int(capture.get("max_results"), "max_results", 1, 16)
            if capture["max_results"] < 2:
                truncated_outputs.add(output)
            outputs.add(output)

    lookups = data.get("lookups", [])
    if not isinstance(lookups, list) or len(lookups) > 8:
        raise ValueError(f"Invalid lookups in {path}")
    for lookup in lookups:
        if lookup.get("input") not in outputs:
            raise ValueError(f"Lookup input is not produced in {path}")
        if "index_path" in lookup:
            validate_remote_path(lookup["index_path"], "index_path")
            if ("{" in lookup["index_path"] or "}" in lookup["index_path"]
                    or "path_template" in lookup or lookup.get("entries_field") != "entries"):
                raise ValueError(f"Stable index must not interpolate captured values in {path}")
        else:
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
            lookup_outputs_by_name.add(output)

    presentation = data.get("presentation", {})
    summary = presentation.get("summary")
    details = presentation.get("details", [])
    if not isinstance(summary, list) or not 1 <= len(summary) <= 2:
        raise ValueError(f"Presentation summary must contain one or two fields in {path}")
    if not isinstance(details, list) or len(details) > 8:
        raise ValueError(f"Invalid presentation details in {path}")
    for item in summary + details:
        if "require_unique" in item:
            if schema_version != 3 or not isinstance(item["require_unique"], bool):
                raise ValueError(f"Invalid require_unique in {path}")
            if item["require_unique"] and item.get("source") in truncated_outputs | lookup_outputs_by_name:
                raise ValueError(f"Unique fields require local captures with max_results >= 2 in {path}")
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


def collect_jetpack_rule_uuids():
    uuids = set()
    for path in ROOT.glob("*-libs/**/*.json"):
        data = load_json(path)
        if not isinstance(data, dict):
            continue
        value = data.get("uuid")
        localized_data = data.get("data")
        if not isinstance(value, str) or not isinstance(localized_data, list):
            continue
        labels = [
            item.get("data", {}).get("label")
            for item in localized_data
            if isinstance(item, dict) and isinstance(item.get("data"), dict)
        ]
        if any(
            isinstance(label, str) and label.startswith("Jetpack ")
            for label in labels
        ) or value == FILE_PROVIDER_UUID:
            uuids.add(value)
    return uuids


def build_catalog():
    rule_uuids = collect_rule_uuids()
    uuid_owners = {}
    native_library_owners = {}
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
        entry = {
            "sdk_id": sdk_id,
            "library_uuids": sorted(target_uuids),
            "definition": relative_path,
        }
        if "native_library_names" in data:
            for name in data["native_library_names"]:
                owner = native_library_owners.setdefault(name, sdk_id)
                if owner != sdk_id:
                    raise ValueError(f"Native library name {name} belongs to both {owner} and {sdk_id}")
            entry["native_library_names"] = data["native_library_names"]
        entries.append(entry)
    if not entries:
        raise ValueError("No SDK detail definitions found")
    if len(entries) > MAX_CATALOG_ENTRIES:
        raise ValueError("Too many SDK detail definitions")
    missing_jetpack_uuids = collect_jetpack_rule_uuids() - uuid_owners.keys()
    if missing_jetpack_uuids:
        raise ValueError(
            "Jetpack rules missing SDK details: "
            + ", ".join(sorted(missing_jetpack_uuids))
        )
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
        generate_androidx_definitions.write()
        changed = write_catalog()
        print("Updated SDK details catalog" if changed else "SDK details catalog is current")
    generate_androidx_definitions.check()
    check_catalog()


if __name__ == "__main__":
    main()
