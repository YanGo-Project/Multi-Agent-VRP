#!/usr/bin/env python3
"""
Склеивает все CSV вида <map>_p*.csv из каталога (например experiments/tdtsp_benchmark)
в один файл для сводного анализа.

Пример:
  python3 scripts/merge_tdtsp_benchmark_csv.py \\
      --input-dir experiments/tdtsp_benchmark --map A \\
      --output experiments/tdtsp_benchmark/A_all_p.csv
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser(description="Объединение A_p10.csv, A_p20.csv, … в один CSV")
    ap.add_argument("--input-dir", type=Path, required=True)
    ap.add_argument("--map", required=True, help="Префикс имён, напр. A")
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()

    d = args.input_dir.resolve()
    if not d.is_dir():
        print(f"Нет каталога: {d}", file=sys.stderr)
        return 1

    pattern = f"{args.map}_p*.csv"
    files = sorted(d.glob(pattern))
    if not files:
        print(f"Нет файлов {pattern} в {d}", file=sys.stderr)
        return 1

    rows: list[dict[str, str]] = []
    fieldnames: list[str] | None = None
    for fp in files:
        with open(fp, encoding="utf-8", newline="") as f:
            r = csv.DictReader(f)
            if fieldnames is None:
                fieldnames = list(r.fieldnames or [])
                if "source_csv" not in fieldnames:
                    fieldnames.append("source_csv")
            for row in r:
                row = dict(row)
                row["source_csv"] = fp.name
                rows.append(row)

    if not fieldnames:
        return 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(f"Записано {len(rows)} строк в {args.output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
