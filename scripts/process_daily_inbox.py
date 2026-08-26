#!/usr/bin/env python3
"""Process approved daily JSON files from the local inbox.

The inbox/archive payloads are intentionally local-only because raw daily input
files may contain private operator context before record_daily.py sanitizes the
public datasets.
"""
import argparse
import datetime as dt
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import record_daily  # noqa: E402

DEFAULT_INPUT_DIR = ROOT / "inbox" / "daily"
DEFAULT_ARCHIVE_DIR = ROOT / "archive" / "daily"
DEFAULT_LOG_FILE = ROOT / "logs" / "daily_inbox_processing.log"


def timestamp():
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def safe_relative(path):
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def load_and_validate(input_path):
    raw = record_daily.read_json(input_path)
    row = record_daily.validate_and_render_row(raw)
    return raw, row


def archive_target(input_path, archive_dir, row):
    month_dir = archive_dir / row["date"][:7]
    target = month_dir / input_path.name
    if not target.exists():
        return target
    stamp = dt.datetime.now().astimezone().strftime("%Y%m%dT%H%M%S%z")
    return month_dir / f"{input_path.stem}-{stamp}{input_path.suffix}"


def append_log(log_file, lines):
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with log_file.open("a", encoding="utf-8") as handle:
        for line in lines:
            handle.write(line + "\n")


def process_file(input_path, archive_dir, dry_run=False):
    _raw, row = load_and_validate(input_path)
    target = archive_target(input_path, archive_dir, row)
    if dry_run:
        return {
            "status": "dry-run-ok",
            "path": input_path,
            "row_id": row["id"],
            "archive_target": target,
            "action": "validated",
        }

    target.parent.mkdir(parents=True, exist_ok=True)
    action, row_id = record_daily.register_daily(input_path)
    shutil.move(str(input_path), str(target))
    return {
        "status": "processed",
        "path": input_path,
        "row_id": row_id,
        "archive_target": target,
        "action": action,
    }


def iter_inputs(input_dir):
    return sorted(path for path in input_dir.glob("*.json") if path.is_file())


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Process approved CEREBRO_DAILY_RECORD JSON files from inbox/daily."
    )
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR, help="Directory containing pending daily JSON files")
    parser.add_argument("--archive-dir", type=Path, default=DEFAULT_ARCHIVE_DIR, help="Directory where processed daily JSON files are archived")
    parser.add_argument("--dry-run", action="store_true", help="Validate files without writing datasets, logs, or moving inputs")
    parser.add_argument("--log-file", type=Path, default=DEFAULT_LOG_FILE, help="Local processing log path; ignored by Git by default")
    args = parser.parse_args(argv)

    inputs = iter_inputs(args.input_dir)
    if not inputs:
        print(f"No daily JSON files found in {safe_relative(args.input_dir)}")
        return 0

    log_lines = []
    failures = 0
    for input_path in inputs:
        try:
            result = process_file(input_path, args.archive_dir, dry_run=args.dry_run)
        except Exception as exc:  # noqa: BLE001 - keep batch processing and report per file.
            failures += 1
            message = f"ERROR {safe_relative(input_path)}: {exc}"
            print(message)
            if not args.dry_run:
                log_lines.append(f"{timestamp()}\tERROR\t{safe_relative(input_path)}\t{exc}")
            continue

        if args.dry_run:
            print(
                "DRY-RUN OK "
                f"{safe_relative(result['path'])}: {result['row_id']} -> {safe_relative(result['archive_target'])}"
            )
        else:
            print(
                "PROCESSED "
                f"{safe_relative(result['path'])}: {result['action']} {result['row_id']} -> {safe_relative(result['archive_target'])}"
            )
            log_lines.append(
                f"{timestamp()}\tPROCESSED\t{safe_relative(result['path'])}\t{result['action']}\t{result['row_id']}\t{safe_relative(result['archive_target'])}"
            )

    if log_lines and not args.dry_run:
        append_log(args.log_file, log_lines)

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
