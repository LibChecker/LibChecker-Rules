import argparse
import json
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[2]
SDKS_DIR = ROOT / "sdk-details" / "sdks"
SCHEMA_VERSION = 2
VERSION_LABEL = {
    "default": "Version",
    "zh-Hans": "版本",
}
DEX_ARCHIVE_PATHS = [
    "classes.dex",
    *[f"classes{index}.dex" for index in range(2, 17)],
]
ANDROIDX_TEST_MODULE_PATHS = [
    "META-INF/androidx.test.core.kotlin_module",
    "META-INF/core_java_androidx_test_core-core_internal_kt.kotlin_module",
    "META-INF/core_java_androidx_test_core-core_kt.kotlin_module",
]


def marker(probe_id, artifact, label=None):
    return {
        "id": probe_id,
        "archive_paths": [f"META-INF/{artifact}.version"],
        "capture": "semver",
        "label": label,
        "max_bytes_per_file": 256,
        "max_total_bytes": 2048,
    }


ANDROIDX_DEFINITIONS = [
    {
        "sdk_id": "androidx_profileinstaller",
        "target_uuids": ["0EA939B4-805A-4D08-9C68-47C745EB49E5"],
        "probes": [
            marker(
                "profileinstaller",
                "androidx.profileinstaller_profileinstaller",
            )
        ],
    },
    {
        "sdk_id": "androidx_media3",
        "target_uuids": [
            "1348B371-85CB-4CDB-9FF1-20734F48AA9E",
            "17C5D1C7-8A5A-412F-8F4D-C16EC303F663",
        ],
        "probes": [
            {
                "id": "media3",
                "archive_paths": DEX_ARCHIVE_PATHS,
                "capture": "prefixed_semver",
                "prefix": "AndroidXMedia3/",
                "max_bytes_per_file": 64 * 1024 * 1024,
                "max_total_bytes": 128 * 1024 * 1024,
            }
        ],
    },
    {
        "sdk_id": "androidx_datastore",
        "target_uuids": ["17B3384C-87CB-4382-80BB-CE10CEA77E50"],
        "probes": [
            marker("datastore_core", "androidx.datastore_datastore-core")
        ],
    },
    {
        "sdk_id": "androidx_lifecycle",
        "target_uuids": ["1987147A-53F5-4C2B-8913-C56CF3C84BA6"],
        "probes": [
            marker("lifecycle_process", "androidx.lifecycle_lifecycle-process")
        ],
    },
    {
        "sdk_id": "androidx_slice",
        "target_uuids": ["41534F7F-505B-4DFA-8298-0BE7DECAE255"],
        "probes": [marker("slice_core", "androidx.slice_slice-core")],
    },
    {
        "sdk_id": "androidx_work",
        "target_uuids": ["42C6F59C-5ABB-442C-A5A1-4638A9BE329D"],
        "probes": [
            marker("work_runtime", "androidx.work_work-runtime", "Runtime"),
            marker(
                "work_multiprocess",
                "androidx.work_work-multiprocess",
                "Multiprocess",
            ),
            marker("work_gcm", "androidx.work_work-gcm", "GCM"),
        ],
    },
    {
        "sdk_id": "androidx_car",
        "target_uuids": ["53E31EB8-9DB5-4B9A-ACE6-35C270EA9FB2"],
        "probes": [marker("car_app", "androidx.car.app_app")],
    },
    {
        "sdk_id": "androidx_startup",
        "target_uuids": ["64206E9E-3C56-4D79-BFBE-9E24C03A6544"],
        "probes": [
            marker("startup_runtime", "androidx.startup_startup-runtime")
        ],
    },
    {
        "sdk_id": "androidx_graphics",
        "target_uuids": ["71464FA3-A55F-4FCE-A805-340482102A77"],
        "probes": [
            marker(
                "graphics_core",
                "androidx.graphics_graphics-core",
                "Graphics Core",
            ),
            marker(
                "graphics_path",
                "androidx.graphics_graphics-path",
                "Graphics Path",
            ),
        ],
    },
    {
        "sdk_id": "androidx_glance",
        "target_uuids": ["744E2A7B-9603-4C80-B0FE-7B9ECC46704E"],
        "probes": [
            marker("glance_appwidget", "androidx.glance_glance-appwidget")
        ],
    },
    {
        "sdk_id": "androidx_camera2",
        "target_uuids": ["79A51827-3838-43F5-8EF6-3BDB6496AC6D"],
        "probes": [
            marker("camera_camera2", "androidx.camera_camera-camera2")
        ],
    },
    {
        "sdk_id": "androidx_fileprovider",
        "target_uuids": ["7B1DA564-ADCF-437B-891E-203CBFF847BE"],
        "probes": [marker("core", "androidx.core_core")],
    },
    {
        "sdk_id": "androidx_tracing",
        "target_uuids": ["7C18D201-2C7B-47BB-AAB1-AD934AC1B253"],
        "probes": [
            marker("tracing_perfetto", "androidx.tracing_tracing-perfetto")
        ],
    },
    {
        "sdk_id": "androidx_sqlite",
        "target_uuids": ["84039219-839B-48EB-98C3-D48AE8BF8B17"],
        "probes": [
            marker("sqlite", "androidx.sqlite_sqlite", "SQLite"),
            marker(
                "sqlite_bundled",
                "androidx.sqlite_sqlite-bundled",
                "SQLite Bundled",
            ),
        ],
    },
    {
        "sdk_id": "androidx_appfunctions",
        "target_uuids": ["8620AC72-DADE-4C50-93F4-20088E23D1A2"],
        "probes": [
            marker(
                "appfunctions_service",
                "androidx.appfunctions_appfunctions-service",
            )
        ],
    },
    {
        "sdk_id": "androidx_test",
        "target_uuids": ["88269B1E-863C-45A3-892B-8D9BC8597589"],
        "probes": [
            {
                "id": "test_core_module",
                "archive_paths": ANDROIDX_TEST_MODULE_PATHS,
                "capture": "sha256",
                "reader": "file_sha256",
                "output": "fingerprints",
                "max_bytes_per_file": 64 * 1024,
                "max_total_bytes": 256 * 1024,
            }
        ],
        "lookups": [
            {
                "input": "fingerprints",
                "path_template": (
                    "sdk-details/sdks/androidx_test/data/fingerprint/{value}.json"
                ),
                "expected_field": "sha256",
                "items_field": "releases",
                "max_requests": 4,
                "max_items": 50,
                "outputs": [
                    {
                        "output": "versions",
                        "field": "version",
                    }
                ],
            }
        ],
    },
    {
        "sdk_id": "androidx_remotecallback",
        "target_uuids": ["8DD8485C-8749-4A20-9862-1DEEC77EB80E"],
        "probes": [
            marker(
                "remotecallback",
                "androidx.remotecallback_remotecallback",
            )
        ],
    },
    {
        "sdk_id": "androidx_room",
        "target_uuids": ["8EE5A226-7511-42CD-985A-DA4418BB5355"],
        "probes": [marker("room_runtime", "androidx.room_room-runtime")],
    },
    {
        "sdk_id": "androidx_credentials",
        "target_uuids": ["A062F89B-0339-484C-B688-BD0FB2B9D76B"],
        "probes": [
            marker(
                "credentials_auth",
                "androidx.credentials_credentials-play-services-auth",
                "Play Services Auth",
            ),
            marker(
                "provider_events",
                (
                    "androidx.credentials.providerevents_"
                    "providerevents-play-services"
                ),
                "Provider Events",
            ),
            marker(
                "registry_provider",
                (
                    "androidx.credentials.registry_"
                    "registry-provider-play-services"
                ),
                "Registry Provider",
            ),
        ],
    },
    {
        "sdk_id": "androidx_media",
        "target_uuids": ["A71F8A7D-AFC4-46D6-BAFE-B17D5D129DFD"],
        "probes": [marker("media", "androidx.media_media")],
    },
    {
        "sdk_id": "androidx_core",
        "target_uuids": ["B4610D43-D1A3-46C1-A55B-CDE665E18CEA"],
        "probes": [
            marker("core", "androidx.core_core", "Core"),
            marker(
                "core_telecom",
                "androidx.core_core-telecom",
                "Core Telecom",
            ),
            marker(
                "core_remoteviews",
                "androidx.core_core-remoteviews",
                "Core RemoteViews",
            ),
        ],
    },
    {
        "sdk_id": "androidx_camera",
        "target_uuids": ["B670C354-BD62-41EB-9FEF-D50E0208EC40"],
        "probes": [marker("camera_core", "androidx.camera_camera-core")],
    },
    {
        "sdk_id": "androidx_webkit",
        "target_uuids": ["BDDF8BDA-550A-44DE-83EF-9111EF333690"],
        "probes": [marker("webkit", "androidx.webkit_webkit")],
    },
    {
        "sdk_id": "androidx_xr",
        "target_uuids": ["C0F66BB0-A2CF-45CD-9DB7-78801E49B9BC"],
        "probes": [
            marker("xr_projected", "androidx.xr.projected_projected")
        ],
    },
    {
        "sdk_id": "androidx_browser",
        "target_uuids": ["C13DA049-9065-40F2-8F53-CB67AE354AFB"],
        "probes": [marker("browser", "androidx.browser_browser")],
    },
    {
        "sdk_id": "androidx_pdf",
        "target_uuids": ["C41E9B74-F8B5-4F97-BCBB-875F610DD3F1"],
        "probes": [
            marker(
                "pdf_document_service",
                "androidx.pdf_pdf-document-service",
                "Document Service",
            ),
            marker(
                "pdf_viewer",
                "androidx.pdf_pdf-viewer",
                "Viewer",
            ),
        ],
    },
    {
        "sdk_id": "androidx_mediarouter",
        "target_uuids": ["C6E84B9F-A3BE-49D7-B1EC-4AB7D5DBF3F1"],
        "probes": [
            marker("mediarouter", "androidx.mediarouter_mediarouter")
        ],
    },
    {
        "sdk_id": "androidx_appcompat",
        "target_uuids": ["D2A17366-5160-4179-BCEC-F88A566BA8DC"],
        "probes": [marker("appcompat", "androidx.appcompat_appcompat")],
    },
    {
        "sdk_id": "androidx_activity",
        "target_uuids": ["DF93DF56-63D0-4D3B-AF4B-39CA3C785A18"],
        "probes": [marker("activity", "androidx.activity_activity")],
    },
    {
        "sdk_id": "androidx_sharetarget",
        "target_uuids": ["E345D252-9789-480A-8D3A-1316A09D142D"],
        "probes": [
            marker("sharetarget", "androidx.sharetarget_sharetarget")
        ],
    },
    {
        "sdk_id": "androidx_compose",
        "target_uuids": ["EFD95ADE-EADB-42FB-9F96-57D47F62FF4F"],
        "probes": [
            marker(
                "ui_tooling",
                "androidx.compose.ui_ui-tooling",
                "UI Tooling",
            ),
            marker(
                "ui_tooling_preview",
                "androidx.compose.ui_ui-tooling-preview",
                "UI Tooling Preview",
            ),
            marker(
                "ui_tooling_data",
                "androidx.compose.ui_ui-tooling-data",
                "UI Tooling Data",
            ),
        ],
    },
]


def capture(probe, output):
    result = {
        "output": output,
        "type": probe["capture"],
        "max_results": 8,
    }
    if probe.get("prefix"):
        result["prefix"] = probe["prefix"]
    return result


def build_probe(probe, include_artifact_output):
    archive_paths = probe["archive_paths"]
    output = probe.get("output", "versions")
    captures = [capture(probe, output)]
    if include_artifact_output and output == "versions":
        captures.append(capture(probe, f"{probe['id']}_versions"))
    return {
        "id": probe["id"],
        "source": {
            "operator": "package_file",
            "file_name": PurePosixPath(archive_paths[0]).name,
            "archive_paths": archive_paths,
        },
        "reader": {
            "operator": probe.get("reader", "ascii_strings"),
            "max_bytes_per_file": probe["max_bytes_per_file"],
            "max_total_bytes": probe["max_total_bytes"],
        },
        "captures": captures,
    }


def build_definition(spec):
    probes = spec["probes"]
    include_artifact_outputs = len(probes) > 1
    definition = {
        "schema_version": SCHEMA_VERSION,
        "sdk_id": spec["sdk_id"],
        "target_uuids": spec["target_uuids"],
        "probes": [
            build_probe(probe, include_artifact_outputs)
            for probe in probes
        ],
    }
    if spec.get("lookups"):
        definition["lookups"] = spec["lookups"]
    definition["presentation"] = {
        "summary": [
            {
                "label": VERSION_LABEL,
                "source": "versions",
                "max_values": 8,
            }
        ]
    }
    if include_artifact_outputs:
        definition["presentation"]["details"] = [
            {
                "label": {
                    "default": probe["label"],
                },
                "source": f"{probe['id']}_versions",
                "max_values": 8,
            }
            for probe in probes
        ]
    return definition


def serialized_definitions():
    return {
        spec["sdk_id"]: json.dumps(
            build_definition(spec),
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
        for spec in ANDROIDX_DEFINITIONS
    }


def check():
    stale = []
    for sdk_id, content in serialized_definitions().items():
        path = SDKS_DIR / sdk_id / "definition.json"
        if not path.exists() or path.read_text(encoding="utf-8") != content:
            stale.append(path.relative_to(ROOT).as_posix())
    if stale:
        raise ValueError(
            "AndroidX definitions are stale; run "
            "generate_androidx_definitions.py --write: "
            + ", ".join(stale)
        )
    print(f"Validated {len(ANDROIDX_DEFINITIONS)} generated AndroidX definitions")


def write():
    changed = 0
    for sdk_id, content in serialized_definitions().items():
        directory = SDKS_DIR / sdk_id
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / "definition.json"
        if path.exists() and path.read_text(encoding="utf-8") == content:
            continue
        temporary = path.with_suffix(".json.tmp")
        temporary.write_text(content, encoding="utf-8")
        temporary.replace(path)
        changed += 1
    print(
        f"Updated {changed} of {len(ANDROIDX_DEFINITIONS)} "
        "generated AndroidX definitions"
    )


def main():
    parser = argparse.ArgumentParser(
        description="Generate remote AndroidX SDK detail definitions"
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--write", action="store_true")
    args = parser.parse_args()
    if args.write:
        write()
    check()


if __name__ == "__main__":
    main()
