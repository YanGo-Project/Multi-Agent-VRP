#!/usr/bin/env python3
"""
Прогон бинарника Multi-Agent-VRP (./build/app) по JSON вида *_ma_demand_K*.json / *_ma_unit_K*.json
и сохранение CSV в том же узком формате, что run_tdtsp_benchmark.py (A_p10.csv, …).

При --avg дополнительно обрабатываются *_ma_demand_avg_K*.json и *_ma_unit_avg_K*.json.

Парсит stdout после секции «=== After local search ===»:
  Agent #0  score=…  time=…  dist=…
  Total score: …

Пример:
  export MA_VRP_BINARY=/path/to/Multi-Agent-VRP/build/app
  python3 scripts/run_ma_benchmark.py --map A --datasets-root datasets/one \\
    --output-dir experiments/ma_benchmark --binary "$MA_VRP_BINARY" --avg
"""
from __future__ import annotations

import argparse
import csv
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

# Общие утилиты из run_tdtsp_benchmark (тот же CSV-формат)
_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from run_tdtsp_benchmark import (  # noqa: E402
    CSV_FIELDS,
    extract_p_from_stem,
    feasible_agents_num_from_after_stats,
    load_instance,
    parse_p_dirname,
    p_to_filename_tag,
    repo_root_from_here,
    summarize_tdtsp_after_json,
)


def default_binary() -> str | None:
    return os.environ.get("MA_VRP_BINARY")


def parse_ma_stdout(text: str) -> dict[str, Any]:
    """Берёт агентов из блока After local search; иначе весь stdout."""
    marker = "=== After local search ==="
    tail = text.split(marker, 1)[1] if marker in text else text

    scores: list[int] = []
    times: list[int] = []
    dists: list[int] = []
    for m in re.finditer(
        r"Agent #\d+\s+score=(-?\d+)\s+time=(\d+)\s+dist=(\d+)",
        tail,
    ):
        scores.append(int(m.group(1)))
        times.append(int(m.group(2)))
        dists.append(int(m.group(3)))

    totals = [int(x) for x in re.findall(r"Total score:\s*(-?\d+)", tail)]
    total_line = totals[-1] if totals else ""

    sum_score = sum(scores) if scores else (total_line if total_line != "" else "")
    return {
        "sum_score": sum_score,
        "sum_time": sum(times) if times else "",
        "sum_distance": sum(dists) if dists else "",
        "total_score_line": total_line,
        "num_agent_blocks": len(scores),
    }


def ma_vertex_bounds(data: dict[str, Any]) -> tuple[int, int]:
    """min_load / max_load в MA — скаляры или массивы по агентам."""
    ml = data["min_load"]
    mx = data["max_load"]
    if isinstance(ml, list):
        min_v = min(int(x) for x in ml) if ml else 0
    else:
        min_v = int(ml)
    if isinstance(mx, list):
        max_v = max(int(x) for x in mx) if mx else 0
    else:
        max_v = int(mx)
    return min_v, max_v


def instance_base_stem_ma(stem: str) -> str:
    """
    Удаляет суффиксы:
      _ma_demand_K<число>
      _ma_demand_avg_K<число>
      _ma_unit_K<число>
      _ma_unit_avg_K<число>
    Возвращает основу для извлечения p.
    """
    m = re.match(r"^(.*)_ma_(demand|unit)(_avg)?_K\d+$", stem)
    return m.group(1) if m else stem


def build_ma_patterns(variant: str, include_avg: bool) -> list[tuple[str, str]]:
    """
    Возвращает список пар (имя_варианта, glob_паттерн).
    Если include_avg == True, то генерирует только avg-паттерны.
    """
    base = {
        "demand": ("demand", "*_ma_demand_K*.json"),
        "unit": ("unit", "*_ma_unit_K*.json"),
    }
    if variant == "both":
        base_variants = ["demand", "unit"]
    else:
        base_variants = [variant]

    patterns = []
    for bv in base_variants:
        name, pattern = base[bv]
        if include_avg:
            # Только avg-версия
            if bv == "demand":
                avg_pattern = "*_ma_demand_avg_K*.json"
            else:
                avg_pattern = "*_ma_unit_avg_K*.json"
            patterns.append((f"{name}_avg", avg_pattern))
        else:
            # Только обычная версия
            patterns.append((name, pattern))
    return patterns


def collect_ma_instances_by_pattern(
    map_dir: Path, pattern: str
) -> list[tuple[Path, float | None, str | None]]:
    """
    Возвращает список (json_path, p_from_parent_dir) для файлов,
    соответствующих glob-паттерну (например "*_ma_demand_*_K*.json").
    Исключает файлы, заканчивающиеся на "_after.json" (результаты прогона).
    """
    out: list[tuple[Path, float | None, str | None]] = []
    for p in sorted(map_dir.iterdir()):
        if not p.is_dir():
            continue
        p_tag_override: str | None = None
        if p.name == "p_full":
            p_val = None
            p_tag_override = "full"
        else:
            p_val = parse_p_dirname(p.name)
        for j in sorted(p.rglob(pattern)):
            if not j.is_file():
                continue
            # Пропускаем после-файлы, созданные солвером
            if j.stem.endswith("_after"):
                continue
            out.append((j, p_val, p_tag_override))
    return out


def run_one_ma(
    binary: Path,
    json_path: Path,
    timeout_sec: float | None,
) -> tuple[int, str, str, float]:
    t0 = time.perf_counter()
    try:
        r = subprocess.run(
            [str(binary), "-p", str(json_path.resolve()), "-i", "20000"],
            capture_output=True,
            text=True,
            timeout=timeout_sec,
        )
        return r.returncode, r.stdout, r.stderr, time.perf_counter() - t0
    except subprocess.TimeoutExpired as e:
        out = e.stdout or ""
        err = (e.stderr or "") + f"\n[timeout after {timeout_sec}s]\n"
        return -124, out, err, time.perf_counter() - t0


def build_row_ma(
    _map_name: str,
    json_path: Path,
    variant: str,
    data: dict[str, Any],
    parsed: dict[str, Any],
    _exit_code: int,
    _elapsed: float,
    _p_override: float | None,
    ma_binary: str | None,
) -> dict[str, Any]:
    stem = json_path.stem
    n = int(data["points_count"])
    v_min, v_max = ma_vertex_bounds(data)
    agents_cnt = int(data.get("agents_count") or data.get("agents_cnt") or 1)

    after_path = json_path.parent / f"{stem}_after.json"
    after_stats = summarize_tdtsp_after_json(after_path, v_min, v_max, agents_cnt)
    fav = feasible_agents_num_from_after_stats(after_stats)

    row: dict[str, Any] = {
        "json_path": str(json_path),
        "variant": variant,
        "sum_score": parsed.get("sum_score", ""),
        "sum_time": parsed.get("sum_time", ""),
        "sum_distance": parsed.get("sum_distance", ""),
        "points_count": n,
        "agents_count": agents_cnt,
        "vertex_min": v_min,
        "vertex_max": v_max,
        "feasible_agents_num": fav,
    }
    if ma_binary is not None:
        row["ma_binary"] = ma_binary
    return row


def main() -> int:
    root = repo_root_from_here()
    ap = argparse.ArgumentParser(
        description="Прогон Multi-Agent-VRP по *_ma_*_K*.json → CSV как у TDTSP-benchmark."
    )
    ap.add_argument("--map", required=True, help="Каталог набора под datasets-root, напр. A")
    ap.add_argument(
        "--datasets-root",
        type=Path,
        default=root / "datasets" / "one",
        help="Родитель каталогов карт (часто datasets/one с подпапками p0.1 …)",
    )
    ap.add_argument(
        "--output-dir",
        type=Path,
        default=root / "experiments" / "ma_benchmark",
        help="Куда писать CSV",
    )
    ap.add_argument(
        "--binary",
        type=Path,
        default=None,
        help="Бинарник Multi-Agent (иначе MA_VRP_BINARY)",
    )
    ap.add_argument(
        "--variant",
        choices=("demand", "unit", "both"),
        default="demand",
        help="*_ma_demand_*_K*.json / *_ma_unit_*_K*.json / оба",
    )
    ap.add_argument(
        "--avg",
        action="store_true",
        help="Дополнительно обрабатывать avg-версии файлов (*_ma_demand_avg_K*.json, *_ma_unit_avg_K*.json)",
    )
    ap.add_argument("--timeout", type=float, default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument(
        "--write-binary-path",
        action="store_true",
        help="Столбец ma_binary",
    )
    args = ap.parse_args()

    map_dir = (args.datasets_root / args.map).resolve()
    if not map_dir.is_dir():
        print(f"Нет каталога: {map_dir}", file=sys.stderr)
        return 1

    bin_path: Path | None = None
    if not args.dry_run:
        bin_path = args.binary
        if bin_path is None:
            bs = default_binary()
            if not bs:
                print(
                    "Укажите --binary или задайте MA_VRP_BINARY на бинарник Multi-Agent-VRP.",
                    file=sys.stderr,
                )
                return 1
            bin_path = Path(bs)
        bin_path = bin_path.resolve()
        if not bin_path.is_file() or not os.access(bin_path, os.X_OK):
            print(f"Бинарник недоступен: {bin_path}", file=sys.stderr)
            return 1

    out_dir = args.output_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    # Получаем список (имя_варианта, glob_паттерн)
    pattern_pairs = build_ma_patterns(args.variant, args.avg)

    # Группируем по p-тегу
    by_p_tag: dict[str, list[tuple[Path, str, float | None]]] = {}
    for vname, pattern in pattern_pairs:
        for json_path, p_dir, p_tag_override in collect_ma_instances_by_pattern(map_dir, pattern):
            base = instance_base_stem_ma(json_path.stem)
            p_stem = extract_p_from_stem(base)
            p_use = p_dir if p_dir is not None else p_stem
            if p_tag_override is not None:
                tag = p_tag_override
            else:
                tag = "unknown" if p_use is None else p_to_filename_tag(float(p_use))
            by_p_tag.setdefault(tag, []).append((json_path, vname, p_use))

    if not by_p_tag:
        print(
            f"Нет файлов, соответствующих паттернам {[p for _,p in pattern_pairs]} под {map_dir}.\n"
            f"Сгенерируйте JSON (build_dataset_json.py) и разложите по p0.1/ …",
            file=sys.stderr,
        )
        return 0 if args.dry_run else 1

    if args.dry_run:
        for tag, items in sorted(by_p_tag.items()):
            csv_path = out_dir / f"{args.map}_p{tag}.csv"
            print(f"{csv_path}  ({len(items)} instances)", file=sys.stderr)
        return 0

    assert bin_path is not None
    fieldnames = list(CSV_FIELDS)
    if args.write_binary_path:
        fieldnames.append("ma_binary")

    for tag, items in sorted(by_p_tag.items()):
        csv_path = out_dir / f"{args.map}_p{tag}.csv"
        rows: list[dict[str, Any]] = []
        for json_path, vname, p_use in sorted(items, key=lambda x: str(x[0])):
            data = load_instance(json_path)
            code, out, err, elapsed = run_one_ma(bin_path, json_path, args.timeout)
            parsed = parse_ma_stdout(out)
            if code != 0 and parsed.get("num_agent_blocks") == 0:
                print(f"WARN exit={code} {json_path}\n{err[:400]}", file=sys.stderr)
            row = build_row_ma(
                args.map,
                json_path,
                vname,
                data,
                parsed,
                code,
                elapsed,
                p_use,
                str(bin_path) if args.write_binary_path else None,
            )
            rows.append(row)

        with open(csv_path, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            w.writeheader()
            w.writerows(rows)
        print(csv_path, len(rows), file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())