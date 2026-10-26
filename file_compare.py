#!/usr/bin/env python3
"""
Compare Active Directory (AD) ITV computer exports with PDQ inventory exports.

Expected filenames in the same folder as this script:
    XXXX-ITV_ad.csv
    XXXX-ITV_pdq.csv

The school prefix (XXXX) is discovered automatically. The script:
- Finds matching AD/PDQ file pairs in its own folder.
- Reads computer names from the "Name" column (or the specified fallback column).
- Compares names case-insensitively, trimming surrounding whitespace and
  removing a trailing DNS domain suffix from fully qualified computer names.
- Produces a detailed text report and a CSV of missing computer names.
- Does not require command-line arguments or additional Python packages.

Run by double-clicking the script or running:
    python compare_itv_inventory.py
"""

from __future__ import annotations

import csv
import re
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable


SCRIPT_DIR = Path(__file__).resolve().parent
AD_SUFFIX = "_ad.csv"
PDQ_SUFFIX = "_pdq.csv"
FILE_STEM_SUFFIX = "-ITV"
REPORT_PREFIX = "ITV_PDQ_Comparison_Report"


@dataclass
class SchoolResult:
    school: str
    ad_file: str
    pdq_file: str
    ad_names: list[str]
    pdq_names: list[str]
    missing_names: list[str]
    ad_unique_count: int
    pdq_unique_count: int
    ad_blank_count: int
    pdq_blank_count: int


def normalize_name(value: str) -> str:
    """Normalize a hostname for comparison without changing its displayed form."""
    name = (value or "").strip().casefold()
    if not name:
        return ""

    # Remove a trailing DNS suffix, e.g. PC123.school.example -> PC123.
    # Do not remove punctuation from the short hostname itself.
    if "." in name:
        name = name.split(".", 1)[0].strip()

    return name


def read_csv_names(path: Path, preferred_column: str, fallback_index: int) -> tuple[list[str], int]:
    """
    Read computer names from a CSV.

    Prefer a column named 'Name' (case-insensitive, whitespace-trimmed).
    If no such header exists, use the documented fallback column index:
      - AD: column A (index 0)
      - PDQ: column B (index 1)
    Returns (non-empty original names, count of blank rows).
    """
    encodings = ("utf-8-sig", "utf-8", "cp1252")
    last_error: Exception | None = None

    for encoding in encodings:
        try:
            with path.open("r", encoding=encoding, newline="") as handle:
                sample = handle.read(8192)
                handle.seek(0)
                try:
                    dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
                except csv.Error:
                    dialect = csv.excel

                rows = list(csv.reader(handle, dialect))
            break
        except UnicodeDecodeError as exc:
            last_error = exc
    else:
        raise RuntimeError(f"Could not decode {path.name}: {last_error}")

    if not rows:
        return [], 0

    header = [cell.strip().casefold() for cell in rows[0]]
    if preferred_column.casefold() in header:
        column_index = header.index(preferred_column.casefold())
        data_rows = rows[1:]
    else:
        column_index = fallback_index
        data_rows = rows

    names: list[str] = []
    blank_count = 0

    for row in data_rows:
        if column_index >= len(row):
            blank_count += 1
            continue
        original = row[column_index].strip()
        if not original:
            blank_count += 1
            continue
        names.append(original)

    return names, blank_count


def find_school_pairs(folder: Path) -> tuple[list[tuple[str, Path, Path]], list[str]]:
    """Discover XXXX-ITV_ad.csv and XXXX-ITV_pdq.csv pairs in folder."""
    ad_files: dict[str, Path] = {}
    pdq_files: dict[str, Path] = {}

    for path in folder.iterdir():
        if not path.is_file():
            continue
        lower_name = path.name.casefold()

        if lower_name.endswith(AD_SUFFIX):
            prefix = path.name[:-len(AD_SUFFIX)]
            if prefix.casefold().endswith(FILE_STEM_SUFFIX.casefold()):
                school = prefix[:-len(FILE_STEM_SUFFIX)]
                if school.strip():
                    ad_files[school.casefold()] = path

        elif lower_name.endswith(PDQ_SUFFIX):
            prefix = path.name[:-len(PDQ_SUFFIX)]
            if prefix.casefold().endswith(FILE_STEM_SUFFIX.casefold()):
                school = prefix[:-len(FILE_STEM_SUFFIX)]
                if school.strip():
                    pdq_files[school.casefold()] = path

    pairs: list[tuple[str, Path, Path]] = []
    warnings: list[str] = []

    for school_key in sorted(set(ad_files) | set(pdq_files)):
        ad_path = ad_files.get(school_key)
        pdq_path = pdq_files.get(school_key)

        display_source = ad_path or pdq_path
        assert display_source is not None
        prefix = display_source.name
        suffix = AD_SUFFIX if ad_path else PDQ_SUFFIX
        school_stem = prefix[:-len(suffix)]
        school = school_stem[:-len(FILE_STEM_SUFFIX)]

        if ad_path and pdq_path:
            pairs.append((school, ad_path, pdq_path))
        elif ad_path:
            warnings.append(
                f"{school}: found {ad_path.name}, but no matching XXXX-ITV_pdq.csv file."
            )
        else:
            warnings.append(
                f"{school}: found {pdq_path.name}, but no matching XXXX-ITV_ad.csv file."
            )

    return pairs, warnings


def compare_school(school: str, ad_path: Path, pdq_path: Path) -> SchoolResult:
    ad_names, ad_blank_count = read_csv_names(ad_path, "Name", 0)
    pdq_names, pdq_blank_count = read_csv_names(pdq_path, "Name", 1)

    ad_keys = {normalize_name(name) for name in ad_names if normalize_name(name)}
    pdq_keys = {normalize_name(name) for name in pdq_names if normalize_name(name)}

    # Keep the first original AD spelling for each normalized name.
    first_ad_name: dict[str, str] = {}
    for name in ad_names:
        key = normalize_name(name)
        if key:
            first_ad_name.setdefault(key, name.strip())

    missing_names = sorted(
        (first_ad_name[key] for key in ad_keys - pdq_keys),
        key=str.casefold,
    )

    return SchoolResult(
        school=school,
        ad_file=ad_path.name,
        pdq_file=pdq_path.name,
        ad_names=ad_names,
        pdq_names=pdq_names,
        missing_names=missing_names,
        ad_unique_count=len(ad_keys),
        pdq_unique_count=len(pdq_keys),
        ad_blank_count=ad_blank_count,
        pdq_blank_count=pdq_blank_count,
    )


def pct(part: int, whole: int) -> str:
    return f"{(part / whole * 100):.1f}%" if whole else "N/A"


def write_reports(results: list[SchoolResult], warnings: list[str], folder: Path) -> tuple[Path, Path]:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    text_path = folder / f"{REPORT_PREFIX}_{timestamp}.txt"
    csv_path = folder / f"{REPORT_PREFIX}_{timestamp}.csv"

    total_ad = sum(r.ad_unique_count for r in results)
    total_pdq = sum(r.pdq_unique_count for r in results)
    total_missing = sum(len(r.missing_names) for r in results)

    lines: list[str] = [
        "ACTIVE DIRECTORY vs. PDQ ITV INVENTORY COMPARISON",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "=" * 64,
        "",
        "EXECUTIVE SUMMARY",
        "-" * 64,
        f"{'School':<16}{'AD unique':>12}{'PDQ unique':>13}{'Missing':>11}{'Missing %':>12}",
    ]

    for result in results:
        missing_count = len(result.missing_names)
        lines.append(
            f"{result.school:<16}{result.ad_unique_count:>12}{result.pdq_unique_count:>13}"
            f"{missing_count:>11}{pct(missing_count, result.ad_unique_count):>12}"
        )

    lines.append("-" * 64)
    lines.append(
        f"{'TOTAL':<16}{total_ad:>12}{total_pdq:>13}{total_missing:>11}"
        f"{pct(total_missing, total_ad):>12}"
    )
    lines.extend([
        "",
        "DETAILS BY SCHOOL",
        "=" * 64,
    ])

    for result in results:
        missing_count = len(result.missing_names)
        lines.extend([
            "",
            f"{result.school} — {missing_count} computer(s) missing from PDQ "
            f"({pct(missing_count, result.ad_unique_count)} of unique AD names)",
            f"Active Directory file: {result.ad_file}",
            f"PDQ file:              {result.pdq_file}",
            f"Unique AD names:       {result.ad_unique_count}",
            f"Unique PDQ names:      {result.pdq_unique_count}",
            f"Missing count:         {missing_count}",
            "",
            "Missing computer names:",
        ])
        if result.missing_names:
            lines.extend(f"  - {name}" for name in result.missing_names)
        else:
            lines.append("  - None")

    lines.extend([
        "",
        "COMPARISON RULES",
        "-" * 64,
        "- Matching is case-insensitive.",
        "- Leading and trailing whitespace is ignored.",
        "- A trailing DNS suffix is removed (e.g. PC123.school.example becomes PC123).",
        "- Otherwise, names are compared exactly; punctuation and numbers are preserved.",
        "- The report counts unique normalized computer names, not duplicate CSV rows.",
        "- AD prefers the header named 'Name'; if absent, it uses column A.",
        "- PDQ prefers the header named 'Name'; if absent, it uses column B.",
        "- Missing means an AD name has no normalized match in its paired PDQ file.",
        "",
        "NOTES",
        "-" * 64,

    ])

    if warnings:
        lines.extend(["", "FILE PAIRING WARNINGS", "-" * 64])
        lines.extend(f"- {warning}" for warning in warnings)

    text_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["School", "Missing Computer Name", "AD File", "PDQ File"])
        for result in results:
            for name in result.missing_names:
                writer.writerow([result.school, name, result.ad_file, result.pdq_file])

    return text_path, csv_path


def main() -> int:
    print("ITV Active Directory vs. PDQ Inventory Comparison")
    print("=" * 50)
    print(f"Looking for matching CSV pairs in:\n{SCRIPT_DIR}\n")

    try:
        pairs, warnings = find_school_pairs(SCRIPT_DIR)

        if not pairs:
            print("No complete file pairs were found.")
            print("Place files such as SCHOOL-ITV_ad.csv and SCHOOL-ITV_pdq.csv")
            print("in the same folder as this script, then run it again.")
            if warnings:
                print("\nFiles found without matching partners:")
                for warning in warnings:
                    print(f"  - {warning}")
            return 1

        results: list[SchoolResult] = []
        for school, ad_path, pdq_path in pairs:
            print(f"Processing {school}: {ad_path.name} + {pdq_path.name}")
            results.append(compare_school(school, ad_path, pdq_path))

        results.sort(key=lambda result: result.school.casefold())
        text_path, csv_path = write_reports(results, warnings, SCRIPT_DIR)

        total_missing = sum(len(result.missing_names) for result in results)
        total_ad = sum(result.ad_unique_count for result in results)

        print("\nSUMMARY")
        print("-" * 50)
        for result in results:
            missing = len(result.missing_names)
            print(
                f"{result.school}: {missing} missing "
                f"({pct(missing, result.ad_unique_count)} of unique AD names)"
            )
        print(f"TOTAL: {total_missing} missing across {total_ad} unique AD names")
        print("\nReports created:")
        print(f"  Detailed text report: {text_path.name}")
        print(f"  Missing names CSV:    {csv_path.name}")

        if warnings:
            print("\nWarnings:")
            for warning in warnings:
                print(f"  - {warning}")

        print("\nDone.")
        return 0

    except (OSError, csv.Error, RuntimeError, ValueError) as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        print("Check that the CSV files are readable and not open in another program.")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())