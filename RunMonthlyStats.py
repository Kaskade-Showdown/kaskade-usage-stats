#!/usr/bin/env python3

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path


MONTH_DIR_RE = re.compile(r"^\d{4}-\d{2}$")

MONOTYPE_TAGS = [
    "mononormal",
    "monofighting",
    "monoflying",
    "monopoison",
    "monoground",
    "monorock",
    "monobug",
    "monoghost",
    "monosteel",
    "monofire",
    "monowater",
    "monograss",
    "monoelectric",
    "monopsychic",
    "monoice",
    "monodragon",
    "monodark",
    "monofairy",
]

SKIPPED_LOG_DIRS = {
    "chat",
    "modlog",
    "randbats",
    "repl",
    "tickets",
}


def run(command):
    print(" ".join(str(part) for part in command), flush=True)
    subprocess.run(command, check=True)


def remove(path):
    if path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()


def reset_generated_workspace(root, python):
    raw = root / "Raw"
    if raw.exists():
        run([python, "clean.py", "all"])
    raw.mkdir(exist_ok=True)

    stats = root / "Stats"
    stats.mkdir(exist_ok=True)

    for path in stats.iterdir():
        if path.is_file():
            path.unlink()
    for dirname in ["chaos", "leads", "metagame", "moveset", "movesets", "monotype"]:
        remove(stats / dirname)

    for path in stats.iterdir():
        if path.is_dir() and path.name != "ratings" and not MONTH_DIR_RE.match(path.name):
            remove(path)

    ratings = stats / "ratings"
    ratings.mkdir(exist_ok=True)


def make_output_folders(root, month):
    month_root = root / "Stats" / month
    remove(month_root)
    for dirname in [
        "",
        "chaos",
        "leads",
        "metagame",
        "moveset",
        "monotype",
        "monotype/chaos",
        "monotype/leads",
        "monotype/matchupcharts",
        "monotype/metagame",
        "monotype/moveset",
    ]:
        (month_root / dirname).mkdir(parents=True, exist_ok=True)


def move_if_exists(source, destination):
    if source.exists():
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            remove(destination)
        shutil.move(str(source), str(destination))


def remove_empty_dirs(path):
    if not path.exists():
        return

    for child in path.iterdir():
        if child.is_dir():
            remove_empty_dirs(child)

    if path.is_dir() and not any(path.iterdir()):
        path.rmdir()


def remove_empty_staging_dirs(root):
    stats = root / "Stats"
    for dirname in ["chaos", "leads", "metagame", "moveset", "movesets", "monotype"]:
        remove_empty_dirs(stats / dirname)


def publish_format_stats(root, month, format_id):
    month_root = root / "Stats" / month

    move_if_exists(root / "Stats" / f"{format_id}-0.txt", month_root / f"{format_id}.txt")
    move_if_exists(root / "Stats" / "chaos" / f"{format_id}-0.json", month_root / "chaos" / f"{format_id}.json")
    move_if_exists(root / "Stats" / "leads" / f"{format_id}-0.txt", month_root / "leads" / f"{format_id}.txt")
    move_if_exists(root / "Stats" / "metagame" / f"{format_id}-0.txt", month_root / "metagame" / f"{format_id}.txt")
    move_if_exists(root / "Stats" / "movesets" / f"{format_id}-0.txt", month_root / "moveset" / f"{format_id}.txt")
    move_if_exists(root / "Stats" / "movesets" / f"{format_id}-0.json", month_root / "moveset" / f"{format_id}.json")
    move_if_exists(root / "Stats" / "movesets" / f"{format_id}-0_calc.txt", month_root / "moveset" / f"{format_id}_calc.txt")


def publish_monotype_stats(root, month, format_id, teamtype):
    month_root = root / "Stats" / month
    source_prefix = f"{format_id}-{teamtype}-0"

    move_if_exists(root / "Stats" / f"{source_prefix}.txt", month_root / "monotype" / f"{teamtype}.txt")
    move_if_exists(root / "Stats" / "chaos" / f"{source_prefix}.json", month_root / "monotype" / "chaos" / f"{teamtype}.json")
    move_if_exists(root / "Stats" / "leads" / f"{source_prefix}.txt", month_root / "monotype" / "leads" / f"{teamtype}.txt")
    move_if_exists(root / "Stats" / "metagame" / f"{source_prefix}.txt", month_root / "monotype" / "metagame" / f"{teamtype}.txt")
    move_if_exists(root / "Stats" / "movesets" / f"{source_prefix}.txt", month_root / "monotype" / "moveset" / f"{teamtype}.txt")
    move_if_exists(root / "Stats" / "movesets" / f"{source_prefix}.json", month_root / "monotype" / "moveset" / f"{teamtype}.json")
    move_if_exists(root / "Stats" / "movesets" / f"{source_prefix}_calc.txt", month_root / "monotype" / "moveset" / f"{teamtype}_calc.txt")


def main():
    parser = argparse.ArgumentParser(description="Generate monthly usage stats for every logged format.")
    parser.add_argument("--log-root", default="../kaskade-showdown/logs")
    parser.add_argument("--months", nargs="*", default=[])
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--node", default="node")
    parser.add_argument(
        "--no-ratings",
        action="store_true",
        help="Include every battle, including unrated/non-ladder games, and skip rating output.",
    )
    args = parser.parse_args()

    root = Path.cwd()
    log_root = Path(args.log_root).resolve()
    selected_months = set(args.months)

    run([args.node, "PS-Extractor.js"])

    month_dirs = sorted(path for path in log_root.iterdir() if path.is_dir() and MONTH_DIR_RE.match(path.name))
    if selected_months:
        month_dirs = [path for path in month_dirs if path.name in selected_months]

    for month_dir in month_dirs:
        month = month_dir.name
        print(f"=== {month} ===", flush=True)

        reset_generated_workspace(root, args.python)
        make_output_folders(root, month)

        for tier_dir in sorted(path for path in month_dir.iterdir() if path.is_dir()):
            format_id = tier_dir.name
            if format_id in SKIPPED_LOG_DIRS:
                print(f"Skipping non-battle logs: {month}/{format_id}", flush=True)
                continue

            print(f"Reading logs: {month}/{format_id}", flush=True)
            if args.no_ratings:
                run([args.python, "batchLogReader.py", str(tier_dir), format_id, "--no-ratings"])
            else:
                ratings_file = root / "Stats" / "ratings" / f"{month}-{format_id}.json"
                remove(ratings_file)
                remove(ratings_file.with_suffix(".txt"))
                run([args.python, "batchLogReader.py", str(tier_dir), format_id, str(ratings_file)])
                if not (root / "Raw" / format_id).exists():
                    remove(ratings_file)
                    remove(ratings_file.with_suffix(".txt"))

        formats = sorted(path.name for path in (root / "Raw").iterdir() if path.is_file())
        for format_id in formats:
            print(f"Writing stats: {month}/{format_id}", flush=True)
            run([args.python, "StatCounter.py", format_id, "0"])
            run([args.python, "batchMovesetCounter.py", format_id, "0"])
            publish_format_stats(root, month, format_id)

        monotype_formats = [format_id for format_id in formats if format_id.endswith("monotype")]
        for format_id in monotype_formats:
            for tag in MONOTYPE_TAGS:
                print(f"Writing monotype stats: {month}/{tag}", flush=True)
                run([args.python, "StatCounter.py", format_id, "0", tag])
                run([args.python, "batchMovesetCounter.py", format_id, "0", tag])
                publish_monotype_stats(root, month, format_id, tag)

        remove_empty_dirs(root / "Stats" / month)
        remove_empty_staging_dirs(root)


if __name__ == "__main__":
    main()
