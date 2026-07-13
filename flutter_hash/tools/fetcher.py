import argparse
import json
import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


FLUTTER_HASH_DIR = Path(__file__).resolve().parent.parent
ENGINE_DIR = FLUTTER_HASH_DIR / "engine"
RELEASE_INDEX_URLS = (
    "https://storage.googleapis.com/flutter_infra_release/releases/releases_linux.json",
    "https://storage.googleapis.com/flutter_infra_release/releases/releases_macos.json",
    "https://storage.googleapis.com/flutter_infra_release/releases/releases_windows.json",
)
ENGINE_VERSION_URL = (
    "https://raw.githubusercontent.com/flutter/flutter/{framework}/bin/internal/engine.version"
)
REVISION_PATTERN = re.compile(r"^[a-f0-9]{40}$")
MAX_WORKERS = 8
MAX_RELEASE_INDEX_BYTES = 8 * 1024 * 1024
MAX_ENGINE_VERSION_BYTES = 128
MAX_TEXT_FIELD_LENGTH = 256
_thread_local = threading.local()


def create_session():
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


def fetch_release_index(session, url):
    with session.get(url, timeout=30, stream=True) as response:
        content = read_limited_response(response, MAX_RELEASE_INDEX_BYTES)
    data = json.loads(content)
    releases = data.get("releases") if isinstance(data, dict) else None
    if not isinstance(releases, list):
        raise ValueError(f"Invalid Flutter release index: {url}")
    return releases


def collect_official_releases(session):
    releases_by_framework = {}
    for url in RELEASE_INDEX_URLS:
        for release in fetch_release_index(session, url):
            if not isinstance(release, dict):
                raise ValueError(f"Invalid release entry in Flutter release index: {url}")
            framework = release.get("hash", "")
            if REVISION_PATTERN.fullmatch(framework):
                current = releases_by_framework.get(framework)
                if current is None or (
                    not current.get("dart_sdk_version") and release.get("dart_sdk_version")
                ):
                    releases_by_framework[framework] = release
    return releases_by_framework


def validate_optional_text(value, field, engine):
    if value is not None and (
        not isinstance(value, str) or len(value) > MAX_TEXT_FIELD_LENGTH
    ):
        raise ValueError(f"Invalid {field} in engine mapping {engine}")


def validate_release(release, engine):
    if not isinstance(release, dict):
        raise ValueError(f"Invalid release in engine mapping {engine}")
    flutter = release.get("flutter")
    framework = release.get("framework")
    if not isinstance(flutter, str) or not flutter or len(flutter) > MAX_TEXT_FIELD_LENGTH:
        raise ValueError(f"Invalid Flutter version in engine mapping {engine}")
    if not isinstance(framework, str) or not REVISION_PATTERN.fullmatch(framework):
        raise ValueError(f"Invalid framework revision in engine mapping {engine}")
    validate_optional_text(release.get("dart"), "Dart version", engine)
    validate_optional_text(release.get("channel"), "channel", engine)
    validate_optional_text(release.get("release_date"), "release date", engine)
    return framework


def validate_mappings(mappings):
    framework_to_engine = {}
    for engine, data in mappings.items():
        if (
            not isinstance(data, dict)
            or not REVISION_PATTERN.fullmatch(engine)
            or data.get("engine") != engine
        ):
            raise ValueError(f"Invalid engine mapping: {engine}")
        releases = data.get("releases")
        if not isinstance(releases, list) or not releases:
            raise ValueError(f"Invalid releases list for engine mapping {engine}")
        seen_frameworks = set()
        for release in releases:
            framework = validate_release(release, engine)
            if framework in seen_frameworks:
                raise ValueError(f"Duplicate framework {framework} in engine mapping {engine}")
            seen_frameworks.add(framework)
            previous = framework_to_engine.setdefault(framework, engine)
            if previous != engine:
                raise ValueError(f"Framework {framework} maps to multiple engines")
    return framework_to_engine


def load_existing_mappings(engine_dir):
    mappings = {}
    if not engine_dir.exists():
        return mappings, {}

    for path in sorted(engine_dir.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        engine = data.get("engine", "")
        if path.stem != engine or not REVISION_PATTERN.fullmatch(engine):
            raise ValueError(f"Invalid engine mapping file: {path}")
        mappings[engine] = data
    return mappings, validate_mappings(mappings)


def fetch_engine_revision(framework):
    with thread_session().get(
        ENGINE_VERSION_URL.format(framework=framework), timeout=30, stream=True
    ) as response:
        content = read_limited_response(response, MAX_ENGINE_VERSION_BYTES)
    engine = content.decode("ascii").strip()
    if not REVISION_PATTERN.fullmatch(engine):
        raise ValueError(f"Invalid engine revision for framework {framework}: {engine!r}")
    return engine


def resolve_missing_engines(frameworks, resolver=fetch_engine_revision):
    resolved = {}
    if not frameworks:
        return resolved
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(resolver, framework): framework for framework in frameworks}
        for future in as_completed(futures):
            framework = futures[future]
            resolved[framework] = future.result()
            print(f"Resolved {framework} -> {resolved[framework]}")
    return resolved


def normalize_release(release):
    normalized = {
        "flutter": release.get("version"),
        "dart": release.get("dart_sdk_version"),
        "channel": release.get("channel"),
        "framework": release.get("hash"),
        "release_date": release.get("release_date"),
    }
    validate_release(normalized, "pending")
    return normalized


def build_mappings(official_releases, existing_mappings, framework_to_engine, resolver=fetch_engine_revision):
    mappings = {
        engine: {"engine": engine, "releases": list(data["releases"])}
        for engine, data in existing_mappings.items()
    }
    missing_frameworks = sorted(set(official_releases) - set(framework_to_engine))
    framework_to_engine = dict(framework_to_engine)
    framework_to_engine.update(resolve_missing_engines(missing_frameworks, resolver))

    for framework, release in official_releases.items():
        engine = framework_to_engine[framework]
        mapping = mappings.setdefault(engine, {"engine": engine, "releases": []})
        releases_by_framework = {
            item.get("framework"): item for item in mapping["releases"]
        }
        releases_by_framework[framework] = normalize_release(release)
        mapping["releases"] = list(releases_by_framework.values())

    for mapping in mappings.values():
        mapping["releases"].sort(
            key=lambda release: (
                release.get("release_date") or "",
                release.get("flutter") or "",
            ),
            reverse=True,
        )
    validate_mappings(mappings)
    return mappings


def write_if_changed(destination, content):
    if destination.exists() and destination.read_text(encoding="utf-8") == content:
        return False
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(destination)
    return True


def write_mappings(mappings, engine_dir):
    validate_mappings(mappings)
    engine_dir.mkdir(parents=True, exist_ok=True)
    changed_files = 0
    for engine, data in sorted(mappings.items()):
        destination = engine_dir / f"{engine}.json"
        content = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
        if write_if_changed(destination, content):
            changed_files += 1
    return changed_files


def parse_args():
    parser = argparse.ArgumentParser(description="Generate Flutter engine mappings")
    parser.add_argument(
        "--check",
        action="store_true",
        help="validate existing engine mappings without network access",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    if args.check:
        mappings, _ = load_existing_mappings(ENGINE_DIR)
        if not mappings:
            raise ValueError(f"No engine mappings found in {ENGINE_DIR}")
        print(
            f"Validated {len(mappings)} engine mappings for "
            f"{sum(len(item['releases']) for item in mappings.values())} releases"
        )
        return

    session = create_session()
    official_releases = collect_official_releases(session)
    existing_mappings, framework_to_engine = load_existing_mappings(ENGINE_DIR)
    mappings = build_mappings(
        official_releases, existing_mappings, framework_to_engine
    )
    changed_engine_files = write_mappings(mappings, ENGINE_DIR)
    print(
        f"Updated {changed_engine_files} of {len(mappings)} engine mappings for "
        f"{sum(len(item['releases']) for item in mappings.values())} releases"
    )


if __name__ == "__main__":
    main()
