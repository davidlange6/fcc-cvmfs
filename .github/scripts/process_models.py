#!/usr/bin/env python3
"""
Process fcc_models package YAML files on PR merge.

For each changed package file:
  - Validates the required fields are present
  - Fails if the version already exists in the summary file
  - Appends the new version to the summary file

Exits non-zero on any error so the workflow step fails visibly.
"""

import sys
import os
import datetime
import argparse
import yaml


REQUIRED_FIELDS = {"package", "version", "source-location"}


def load_yaml(path):
    with open(path) as f:
        return yaml.safe_load(f)


def summary_path(models_dir, package_name):
    return os.path.join(models_dir, f"summary_{package_name}.yml")


def validate_package_file(data, path):
    missing = REQUIRED_FIELDS - set(data.keys())
    if missing:
        raise ValueError(f"{path}: missing required fields: {missing}")
    if os.path.basename(path).startswith("summary_"):
        raise ValueError(f"{path}: summary files must not be passed as package files")


def check_and_update_summary(models_dir, package_file, dry_run=False):
    data = load_yaml(package_file)
    validate_package_file(data, package_file)

    package = data["package"]
    version = str(data["version"])
    source = data["source-location"]

    spath = summary_path(models_dir, package)

    if os.path.exists(spath):
        summary = load_yaml(spath)
        existing_versions = [str(v["version"]) for v in summary.get("versions", [])]
        if version in existing_versions:
            raise ValueError(
                f"Version {version!r} of package {package!r} already exists in {spath}. "
                "Bump the version or remove the duplicate entry."
            )
    else:
        summary = {"package": package, "versions": []}

    new_entry = {
        "version": version,
        "source-location": source,
        "added": datetime.date.today().isoformat(),
    }
    summary["versions"].append(new_entry)

    if not dry_run:
        with open(spath, "w") as f:
            yaml.dump(summary, f, default_flow_style=False, sort_keys=False)
        print(f"Updated {spath}")

    return spath


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("package_files", nargs="+", help="Package YAML files to process")
    parser.add_argument("--models-dir", default="fcc_models", help="Path to fcc_models directory")
    parser.add_argument("--dry-run", action="store_true", help="Validate only, do not write")
    args = parser.parse_args()

    updated_summaries = []
    errors = []

    for pfile in args.package_files:
        try:
            spath = check_and_update_summary(args.models_dir, pfile, dry_run=args.dry_run)
            updated_summaries.append(spath)
        except Exception as e:
            errors.append(str(e))
            print(f"ERROR: {e}", file=sys.stderr)

    if errors:
        print(f"\n{len(errors)} error(s) found. Aborting.", file=sys.stderr)
        sys.exit(1)

    # Emit updated summary paths for the workflow to pick up
    summary_list = "\n".join(updated_summaries)
    print(f"\nUpdated summaries:\n{summary_list}")

    # Write to GITHUB_OUTPUT if available
    gho = os.environ.get("GITHUB_OUTPUT")
    if gho:
        with open(gho, "a") as f:
            f.write(f"updated_summaries={' '.join(updated_summaries)}\n")


if __name__ == "__main__":
    main()
