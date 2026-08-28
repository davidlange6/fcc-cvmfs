#!/usr/bin/env python3
"""
Process fcc_models package YAML files on PR merge (or dry-run on PR open).

Each submission file contains a `packages` list. For each entry:
  - Validates required fields are present
  - Fails if the version already exists in the summary file

All entries in a file are validated before any summaries are written (atomic).
On success (non-dry-run), summaries are updated and the submission file is deleted.

Exit codes:
  0 — all good
  1 — one or more validation errors
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


def normalize_sources(entry):
    """Return source-location as a list regardless of whether it was a string or list."""
    src = entry["source-location"]
    return src if isinstance(src, list) else [src]


def validate_entry(entry, source_file):
    """Validate one package entry; return an error string or None."""
    missing = REQUIRED_FIELDS - set(entry.keys())
    if missing:
        return f"{source_file}: missing required fields: {sorted(missing)}"
    src = entry["source-location"]
    if not isinstance(src, (str, list)) or (isinstance(src, list) and not src):
        return f"{source_file}: `source-location` must be a URL string or a non-empty list of URLs"
    if "readme" in entry and not isinstance(entry["readme"], str):
        return f"{source_file}: `readme` must be a string"
    return None


def check_duplicate(models_dir, entry, source_file):
    """Return an error string if the version already exists in the summary, else None."""
    package = entry["package"]
    version = str(entry["version"])
    spath = summary_path(models_dir, package)
    if os.path.exists(spath):
        summary = load_yaml(spath)
        existing = [str(v["version"]) for v in summary.get("versions", [])]
        if version in existing:
            return (
                f"{source_file}: version {version!r} of package {package!r} "
                f"already exists in {spath}"
            )
    return None


def update_summary(models_dir, entry):
    """Append the entry to its summary file, creating it if needed."""
    package = entry["package"]
    version = str(entry["version"])
    spath = summary_path(models_dir, package)

    if os.path.exists(spath):
        summary = load_yaml(spath)
    else:
        summary = {"package": package, "versions": []}

    record = {
        "version": version,
        "source-location": entry["source-location"],
        "added": datetime.date.today().isoformat(),
    }
    if "readme" in entry:
        record["readme"] = entry["readme"]
    summary["versions"].append(record)

    with open(spath, "w") as f:
        yaml.dump(summary, f, default_flow_style=False, sort_keys=False)

    return spath


def process_file(models_dir, submission_file, dry_run):
    """
    Validate all entries in submission_file atomically, then (if not dry_run)
    write summaries and delete the submission file.

    Returns (ok: bool, messages: list[str], updated_summaries: list[str])
    """
    data = load_yaml(submission_file)

    if "packages" not in data or not isinstance(data["packages"], list):
        return False, [f"{submission_file}: must contain a top-level `packages` list"], []

    entries = data["packages"]
    if not entries:
        return False, [f"{submission_file}: `packages` list is empty"], []

    # --- validation pass (touch nothing yet) ---
    errors = []
    for entry in entries:
        err = validate_entry(entry, submission_file)
        if err:
            errors.append(err)
            continue
        err = check_duplicate(models_dir, entry, submission_file)
        if err:
            errors.append(err)

    if errors:
        return False, errors, []

    # --- write pass ---
    messages = []
    updated_summaries = []

    if not dry_run:
        for entry in entries:
            spath = update_summary(models_dir, entry)
            updated_summaries.append(spath)
            messages.append(f"  updated {spath}")
        os.remove(submission_file)
        messages.append(f"  removed {submission_file}")
    else:
        for entry in entries:
            sources = normalize_sources(entry)
            src_display = sources[0] if len(sources) == 1 else f"{len(sources)} files"
            messages.append(
                f"  OK: {entry['package']} v{entry['version']} ({src_display})"
            )

    return True, messages, updated_summaries


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("submission_files", nargs="+", help="Submission YAML files to process")
    parser.add_argument("--models-dir", default="fcc_models")
    parser.add_argument("--dry-run", action="store_true", help="Validate only; do not write")
    parser.add_argument(
        "--output-format",
        choices=["text", "markdown"],
        default="text",
        help="Output format (markdown for PR comments)",
    )
    args = parser.parse_args()

    all_ok = True
    all_updated_summaries = []
    report_lines = []

    for sfile in args.submission_files:
        ok, messages, updated = process_file(args.models_dir, sfile, args.dry_run)
        all_ok = all_ok and ok
        all_updated_summaries.extend(updated)

        if args.output_format == "markdown":
            icon = "✅" if ok else "❌"
            report_lines.append(f"{icon} **`{sfile}`**")
            for m in messages:
                report_lines.append(f"  - {m.strip()}")
        else:
            status = "OK" if ok else "FAILED"
            print(f"[{status}] {sfile}")
            for m in messages:
                print(m)

    if args.output_format == "markdown":
        header = (
            "### FCC Models — validation passed ✅"
            if all_ok
            else "### FCC Models — validation failed ❌"
        )
        note = (
            "_On merge: summaries will be updated and submission files removed._"
            if all_ok and args.dry_run
            else ""
        )
        print("\n".join([header, ""] + report_lines + (["", note] if note else [])))

    if not all_ok:
        sys.exit(1)

    # Emit updated summary paths for the workflow
    gho = os.environ.get("GITHUB_OUTPUT")
    if gho and all_updated_summaries:
        with open(gho, "a") as f:
            f.write(f"updated_summaries={' '.join(all_updated_summaries)}\n")


if __name__ == "__main__":
    main()
