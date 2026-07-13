import argparse
import importlib.util
from pathlib import Path

import validate


SDKS_DIR = Path(__file__).resolve().parents[1] / "sdks"


def load_providers():
    providers = {}
    for path in sorted(SDKS_DIR.glob("*/provider.py")):
        module_name = f"sdk_details_provider_{path.parent.name}"
        spec = importlib.util.spec_from_file_location(module_name, path)
        if spec is None or spec.loader is None:
            raise ValueError(f"Unable to load provider: {path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        sdk_id = getattr(module, "SDK_ID", None)
        if sdk_id != path.parent.name:
            raise ValueError(f"Provider SDK_ID must match directory name: {path}")
        if sdk_id in providers:
            raise ValueError(f"Duplicate SDK details provider: {sdk_id}")
        if not callable(getattr(module, "update", None)) or not callable(
            getattr(module, "validate", None)
        ):
            raise ValueError(f"Provider must expose update() and validate(): {path}")
        providers[sdk_id] = module
    return providers


def main():
    parser = argparse.ArgumentParser(description="Update generated SDK detail data")
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--all", action="store_true", help="update every provider")
    selection.add_argument("--sdk", help="update one SDK provider")
    selection.add_argument("--check", action="store_true", help="validate without network access")
    args = parser.parse_args()

    providers = load_providers()
    if args.check:
        for provider in providers.values():
            provider.validate()
        validate.check_catalog()
        return

    selected = providers
    if args.sdk:
        if args.sdk not in providers:
            raise ValueError(f"Unknown SDK details provider: {args.sdk}")
        selected = {args.sdk: providers[args.sdk]}
    elif not args.all:
        parser.error("choose --all, --sdk, or --check")

    validate.write_catalog()
    for sdk_id, provider in selected.items():
        print(f"Updating SDK details provider: {sdk_id}")
        provider.update()
        provider.validate()
    validate.check_catalog()


if __name__ == "__main__":
    main()
