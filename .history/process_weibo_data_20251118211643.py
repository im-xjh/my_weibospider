#!/usr/bin/env python3
"""
Process Weibo JSONL data for the “数字中国建设峰会” dataset:

1. Deduplicate records by `_id` and write a `_cleaned.jsonl` file next to the source.
2. Save original posts to `data/original_posts.csv`.
3. Save retweets sorted by `retweet_id` to `data/retweets_by_source.csv`.
4. For comment crawling, export original posts with comments to both CSV/JSONL under `data/`.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Dict, Iterable, List, Sequence


INPUT_FILE = Path("output/数据要素大赛.jsonl")
CLEANED_FILE = INPUT_FILE.with_name(f"{INPUT_FILE.stem}_cleaned.jsonl")
DATA_DIR = Path("data数据要素")

ORIGINAL_FIELDS: Sequence[str] = (
    "_id",
    "mblogid",
    "created_at",
    "ip_location",
    "reposts_count",
    "comments_count",
    "attitudes_count",
    "source",
    "isLongText",
    "pic_num",
    "keyword",
    "url",
    "user_id",
    "user_name",
    "user_verified",
    "content",
)

RETWEET_FIELDS: Sequence[str] = ORIGINAL_FIELDS[:-1] + ("retweet_id", "content")

COMMENT_FIELDS: Sequence[str] = (
    "mblogid",
    "_id",
    "url",
    "comments_count",
    "user_id",
    "user_name",
    "content",
)


def load_jsonl(path: Path) -> List[Dict]:
    entries: List[Dict] = []
    with path.open("r", encoding="utf-8") as infile:
        for line in infile:
            line = line.strip()
            if not line:
                continue
            entries.append(json.loads(line))
    return entries


def dedupe_by_id(entries: Iterable[Dict], key: str = "_id") -> List[Dict]:
    seen = set()
    cleaned: List[Dict] = []
    for entry in entries:
        identifier = entry.get(key)
        if identifier is None or identifier not in seen:
            cleaned.append(entry)
        if identifier is not None:
            seen.add(identifier)
    return cleaned


def write_jsonl(entries: Iterable[Dict], path: Path) -> None:
    with path.open("w", encoding="utf-8") as outfile:
        for entry in entries:
            outfile.write(json.dumps(entry, ensure_ascii=False))
            outfile.write("\n")


def flatten_entry(entry: Dict) -> Dict:
    user = entry.get("user") or {}
    return {
        "_id": entry.get("_id"),
        "mblogid": entry.get("mblogid"),
        "created_at": entry.get("created_at"),
        "ip_location": entry.get("ip_location"),
        "reposts_count": entry.get("reposts_count"),
        "comments_count": entry.get("comments_count"),
        "attitudes_count": entry.get("attitudes_count"),
        "source": entry.get("source"),
        "isLongText": entry.get("isLongText"),
        "pic_num": entry.get("pic_num"),
        "keyword": entry.get("keyword"),
        "url": entry.get("url"),
        "user_id": user.get("_id"),
        "user_name": user.get("nick_name"),
        "user_verified": user.get("verified"),
        "content": entry.get("content"),
        "retweet_id": entry.get("retweet_id"),
    }


def write_csv(rows: Iterable[Dict], fieldnames: Sequence[str], path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as outfile:
        writer = csv.DictWriter(outfile, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key) for key in fieldnames})


def main() -> None:
    if not INPUT_FILE.exists():
        raise FileNotFoundError(f"Input file not found: {INPUT_FILE}")

    DATA_DIR.mkdir(exist_ok=True)

    entries = load_jsonl(INPUT_FILE)
    deduped = dedupe_by_id(entries)
    write_jsonl(deduped, CLEANED_FILE)

    flattened = [flatten_entry(entry) for entry in deduped]

    original_entries = [row for row, entry in zip(flattened, deduped) if not entry.get("is_retweet", False)]
    write_csv(original_entries, ORIGINAL_FIELDS, DATA_DIR / "original_posts.csv")

    retweet_entries = [
        row for row, entry in zip(flattened, deduped) if entry.get("is_retweet", False)
    ]
    retweet_entries.sort(key=lambda row: row.get("retweet_id") or "")
    write_csv(retweet_entries, RETWEET_FIELDS, DATA_DIR / "retweets_by_source.csv")

    comment_targets = [
        {key: row.get(key) for key in COMMENT_FIELDS}
        for row in original_entries
        if (row.get("comments_count") or 0) > 0
    ]
    comment_csv = DATA_DIR / "comment_fetch_targets.csv"
    comment_jsonl = DATA_DIR / "comment_fetch_targets.jsonl"
    write_csv(comment_targets, COMMENT_FIELDS, comment_csv)
    write_jsonl(comment_targets, comment_jsonl)

    print(f"Deduped records: {len(deduped)} (from {len(entries)})")
    print(f"Original posts: {len(original_entries)}")
    print(f"Retweet posts: {len(retweet_entries)}")
    print(f"Comment targets: {len(comment_targets)}")
    print(f"- CSV: {comment_csv}")
    print(f"- JSONL: {comment_jsonl}")
    print(f"Cleaned file written to {CLEANED_FILE}")
    print(f"Data outputs available in {DATA_DIR.resolve()}")


if __name__ == "__main__":
    main()
