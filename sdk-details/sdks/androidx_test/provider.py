import hashlib
import io
import json
import re
import threading
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from xml.etree import ElementTree


SDK_DIR = Path(__file__).resolve().parent
FINGERPRINT_DIR = SDK_DIR / "data" / "fingerprint"
DEFINITION_PATH = SDK_DIR / "definition.json"
SDK_ID = "androidx_test"
GROUP_INDEX_URL = (
    "https://dl.google.com/dl/android/maven2/androidx/test/group-index.xml"
)
AAR_URL = (
    "https://dl.google.com/dl/android/maven2/androidx/test/core/"
    "{version}/core-{version}.aar"
)
VERSION_PATTERN = re.compile(
    r"^([0-9]+)\.([0-9]+)\.([0-9]+)(?:-([0-9A-Za-z][0-9A-Za-z.-]*))?$"
)
SHA256_PATTERN = re.compile(r"^[a-f0-9]{64}$")
MAX_WORKERS = 8
MAX_GROUP_INDEX_BYTES = 512 * 1024
MAX_AAR_BYTES = 16 * 1024 * 1024
MAX_CLASSES_JAR_BYTES = 16 * 1024 * 1024
MAX_MODULE_BYTES = 64 * 1024
MAX_TEXT_FIELD_LENGTH = 256
_thread_local = threading.local()


def create_session():
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry

    session = requests.Session()
    retry = Retry(
        total=4,
        backoff_factor=0.5,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
    )
    session.mount("https://", HTTPAdapter(max_retries=retry))
    return session


def thread_session():
    session = getattr(_thread_local, "session", None)
    if session is None:
        session = create_session()
        _thread_local.session = session
    return session


def read_limited_response(response, max_bytes):
    response.raise_for_status()
    content = response.raw.read(max_bytes + 1, decode_content=True)
    if len(content) > max_bytes:
        raise ValueError(f"Response from {response.url} exceeds {max_bytes} bytes")
    return content


def parse_versions(content):
    root = ElementTree.fromstring(content)
    core = root.find("core")
    versions = core.get("versions", "").split(",") if core is not None else []
    if not versions or any(not VERSION_PATTERN.fullmatch(version) for version in versions):
        raise ValueError("Invalid AndroidX Test core version index")
    return versions


def fetch_versions(session):
    with session.get(
        GROUP_INDEX_URL,
        timeout=30,
        stream=True,
    ) as response:
        return parse_versions(
            read_limited_response(response, MAX_GROUP_INDEX_BYTES)
        )


def read_zip_entry(archive, name, max_bytes):
    info = archive.getinfo(name)
    if info.file_size > max_bytes:
        raise ValueError(f"{name} exceeds {max_bytes} bytes")
    content = archive.read(info)
    if len(content) > max_bytes:
        raise ValueError(f"{name} exceeds {max_bytes} bytes")
    return content


def fingerprint_aar(content):
    if len(content) > MAX_AAR_BYTES:
        raise ValueError("AndroidX Test AAR exceeds the size limit")
    with zipfile.ZipFile(io.BytesIO(content)) as aar:
        classes = read_zip_entry(aar, "classes.jar", MAX_CLASSES_JAR_BYTES)
    fingerprints = []
    with zipfile.ZipFile(io.BytesIO(classes)) as jar:
        for name in sorted(jar.namelist()):
            if not (
                name.startswith("META-INF/")
                and name.endswith(".kotlin_module")
            ):
                continue
            module = read_zip_entry(jar, name, MAX_MODULE_BYTES)
            fingerprints.append((name, hashlib.sha256(module).hexdigest()))
    return fingerprints


def fetch_version_fingerprints(version):
    url = AAR_URL.format(version=version)
    with thread_session().get(url, timeout=30, stream=True) as response:
        content = read_limited_response(response, MAX_AAR_BYTES)
    return fingerprint_aar(content)


def collect_fingerprints(versions, fetcher=fetch_version_fingerprints):
    results = {}
    if not versions:
        return results
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(fetcher, version): version
            for version in versions
        }
        for future in as_completed(futures):
            version = futures[future]
            results[version] = future.result()
            print(
                f"Resolved AndroidX Test {version}: "
                f"{len(results[version])} module fingerprints"
            )
    return results


def validate_release(release, digest):
    if not isinstance(release, dict):
        raise ValueError(f"Invalid release in fingerprint mapping {digest}")
    version = release.get("version")
    artifact = release.get("artifact")
    entry = release.get("entry")
    if not isinstance(version, str) or not VERSION_PATTERN.fullmatch(version):
        raise ValueError(f"Invalid version in fingerprint mapping {digest}")
    if artifact != "core":
        raise ValueError(f"Invalid artifact in fingerprint mapping {digest}")
    if (
        not isinstance(entry, str)
        or not entry.startswith("META-INF/")
        or not entry.endswith(".kotlin_module")
        or len(entry) > MAX_TEXT_FIELD_LENGTH
    ):
        raise ValueError(f"Invalid entry in fingerprint mapping {digest}")
    return artifact, version, entry


def validate_mappings(mappings):
    for digest, data in mappings.items():
        if (
            not isinstance(data, dict)
            or not SHA256_PATTERN.fullmatch(digest)
            or data.get("sha256") != digest
        ):
            raise ValueError(f"Invalid AndroidX Test fingerprint mapping: {digest}")
        releases = data.get("releases")
        if not isinstance(releases, list) or not releases:
            raise ValueError(f"Invalid releases in fingerprint mapping {digest}")
        identities = [validate_release(release, digest) for release in releases]
        if len(identities) != len(set(identities)):
            raise ValueError(f"Duplicate release in fingerprint mapping {digest}")


def load_existing_mappings(fingerprint_dir):
    mappings = {}
    if not fingerprint_dir.exists():
        return mappings
    for path in sorted(fingerprint_dir.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        digest = data.get("sha256", "")
        if path.stem != digest:
            raise ValueError(f"Fingerprint filename does not match content: {path}")
        mappings[digest] = data
    validate_mappings(mappings)
    return mappings


def build_mappings(resolved, existing=None):
    mappings = {
        digest: {
            "sha256": digest,
            "releases": list(data["releases"]),
        }
        for digest, data in (existing or {}).items()
    }
    for version, fingerprints in resolved.items():
        for entry, digest in fingerprints:
            mapping = mappings.setdefault(
                digest,
                {
                    "sha256": digest,
                    "releases": [],
                },
            )
            releases = {
                (
                    release["artifact"],
                    release["version"],
                    release["entry"],
                ): release
                for release in mapping["releases"]
            }
            identity = ("core", version, entry)
            releases[identity] = {
                "artifact": "core",
                "version": version,
                "entry": entry,
            }
            mapping["releases"] = list(releases.values())
    for mapping in mappings.values():
        mapping["releases"].sort(
            key=lambda release: (
                version_sort_key(release["version"]),
                release["artifact"],
                release["entry"],
            ),
            reverse=True,
        )
    validate_mappings(mappings)
    return mappings


def version_sort_key(version):
    match = VERSION_PATTERN.fullmatch(version)
    if match is None:
        raise ValueError(f"Invalid AndroidX Test version: {version}")
    prerelease = match.group(4)
    normalized_prerelease = re.sub(
        r"[0-9]+",
        lambda value: value.group().zfill(12),
        prerelease or "",
    )
    return (
        int(match.group(1)),
        int(match.group(2)),
        int(match.group(3)),
        prerelease is None,
        normalized_prerelease,
    )


def write_if_changed(destination, content):
    if destination.exists() and destination.read_text(encoding="utf-8") == content:
        return False
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(destination)
    return True


def write_mappings(mappings, fingerprint_dir):
    validate_mappings(mappings)
    fingerprint_dir.mkdir(parents=True, exist_ok=True)
    changed = 0
    for digest, data in sorted(mappings.items()):
        content = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
        if write_if_changed(fingerprint_dir / f"{digest}.json", content):
            changed += 1
    return changed


def definition_archive_paths():
    definition = json.loads(DEFINITION_PATH.read_text(encoding="utf-8"))
    probes = definition.get("probes")
    if not isinstance(probes, list) or len(probes) != 1:
        raise ValueError("Invalid AndroidX Test definition")
    source = probes[0].get("source")
    paths = source.get("archive_paths") if isinstance(source, dict) else None
    if not isinstance(paths, list) or not paths:
        raise ValueError("Invalid AndroidX Test module paths")
    return set(paths)


def validate_definition_paths(mappings):
    configured = definition_archive_paths()
    discovered = {
        release["entry"]
        for mapping in mappings.values()
        for release in mapping["releases"]
    }
    missing = discovered - configured
    if missing:
        raise ValueError(
            "AndroidX Test definition is missing module paths: "
            + ", ".join(sorted(missing))
        )


def validate():
    mappings = load_existing_mappings(FINGERPRINT_DIR)
    if not mappings:
        raise ValueError(f"No AndroidX Test mappings found in {FINGERPRINT_DIR}")
    validate_definition_paths(mappings)
    print(
        f"Validated {len(mappings)} AndroidX Test fingerprints for "
        f"{sum(len(item['releases']) for item in mappings.values())} releases"
    )


def update():
    versions = fetch_versions(create_session())
    resolved = collect_fingerprints(versions)
    existing = load_existing_mappings(FINGERPRINT_DIR)
    mappings = build_mappings(resolved, existing)
    validate_definition_paths(mappings)
    changed = write_mappings(mappings, FINGERPRINT_DIR)
    print(
        f"Updated {changed} of {len(mappings)} AndroidX Test fingerprints for "
        f"{sum(len(item['releases']) for item in mappings.values())} releases"
    )
