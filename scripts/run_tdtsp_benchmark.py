#!/usr/bin/env python3
"""
Запуск TDTSP-PD по JSON-инстансам (например datasets/many/A/p0.1/*_tdtsp_base_*.json)
и сохранение сводки в CSV по карте и p:  A_p10.csv  (p=0.1 → «10»).
Подкаталог ``p_full`` даёт отдельный файл ``<map>_pfull.csv`` (как в run_ma_benchmark.py).

Поддерживаются обычные файлы (*_tdtsp_base_demand.json, *_tdtsp_base_unit.json)
и их avg-версии (*_tdtsp_base_demand_avg.json, *_tdtsp_base_unit_avg.json)
при использовании флага --avg.

Пример:
  export TDTSP_PD_BINARY=/path/to/TDTSP-PD/build/tdtsp
  python3 scripts/run_tdtsp_benchmark.py --map A --datasets-root datasets/many --avg

Столбцы CSV (одна строка на инстанс): json_path, variant, sum_score, sum_time, sum_distance,
points_count, agents_count, vertex_min, vertex_max, feasible_agents_num.
Датасет, карта и p задаются именем файла (A_p10.csv) и путём в json_path.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


def repo_root_from_here() -> Path:
    return Path(__file__).resolve().parents[1]


def default_binary() -> str | None:
    return os.environ.get("TDTSP_PD_BINARY")


def parse_tdtsp_stdout(text: str) -> dict[str, Any]:
    """
    Суммирует по всем блокам «Solution score/time/dist» и берёт total из «===SCORE = X ===».
    """
    scores = [int(m.group(1)) for m in re.finditer(r"Solution score:\s*(-?\d+)", text)]
    times = [int(m.group(1)) for m in re.finditer(r"Solution time:\s*(\d+)", text)]
    dists = [int(m.group(1)) for m in re.finditer(r"Solution dist:\s*(\d+)", text)]
    total_m = re.search(r"===SCORE\s*=\s*(-?\d+)\s*===", text)
    total_score = int(total_m.group(1)) if total_m else sum(scores)

    n_blocks = min(len(scores), len(times), len(dists))
    return {
        "per_agent_score": scores[:n_blocks],
        "per_agent_time": times[:n_blocks],
        "per_agent_dist": dists[:n_blocks],
        "sum_score": sum(scores[:n_blocks]) if scores else total_score,
        "sum_time": sum(times[:n_blocks]) if times else "",
        "sum_distance": sum(dists[:n_blocks]) if dists else "",
        "total_score_line": int(total_m.group(1)) if total_m else "",
        "num_agent_blocks": n_blocks,
    }


def load_instance(path: Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def scalar_int(data: dict[str, Any], key: str) -> int:
    v = data[key]
    if isinstance(v, list):
        if not v:
            raise ValueError(f"{key}: пустой массив")
        return int(v[0])
    return int(v)


def feasible_k_range(clients: int, v_min: int, v_max: int) -> tuple[int, int] | None:
    """K такие, что K·v_min ≤ |C| ≤ K·v_max."""
    if v_min <= 0 or v_max <= 0 or clients < 0:
        return None
    k_lo = (clients + v_max - 1) // v_max
    k_hi = clients // v_min
    if k_lo > k_hi or k_hi < 1:
        return None
    return max(1, k_lo), k_hi


def constraints_ok_for_k(clients: int, v_min: int, v_max: int, k: int) -> bool:
    r = feasible_k_range(clients, v_min, v_max)
    if r is None:
        return False
    k_lo, k_hi = r
    return k_lo <= k <= k_hi


def parse_p_dirname(dirname: str) -> float | None:
    if dirname.startswith("p"):
        try:
            return float(dirname[1:].replace("_", "."))
        except ValueError:
            return None
    return None


def p_to_filename_tag(p: float) -> str:
    """0.1 → '10', 0.25 → '25' (целые проценты)."""
    return str(round(p * 100))


def extract_p_from_stem(stem: str) -> float | None:
    m = re.search(r"_p([0-9]+(?:\.[0-9]+)?)", stem)
    if not m:
        return None
    try:
        return float(m.group(1))
    except ValueError:
        return None


def instance_base_stem(json_stem: str) -> str:
    """Удаляет суффикс _tdtsp_base_(demand|unit)(_avg)? и возвращает основу."""
    pattern = r"_tdtsp_base_(demand|unit)(_avg)?$"
    return re.sub(pattern, "", json_stem)


def map_name_from_json_path(path: str) -> str:
    """Имя карты из пути …/datasets/<набор>/<карта>/p…/file.json."""
    s = path.replace("\\", "/")
    m = re.search(r"/datasets/[^/]+/([^/]+)/", s)
    return m.group(1) if m else ""


def p_value_from_json_path(path: str) -> float | None:
    """p из каталога p0.1 / p0_25 или из суффикса _p0.1 в имени файла."""
    s = path.replace("\\", "/")
    m = re.search(r"/p([0-9]+(?:_[0-9]+)?)/", s)
    if m:
        try:
            return float(m.group(1).replace("_", "."))
        except ValueError:
            pass
    stem = Path(path).stem
    return extract_p_from_stem(stem)


CSV_FIELDS = [
    "json_path",
    "variant",
    "sum_score",
    "sum_time",
    "sum_distance",
    "points_count",
    "agents_count",
    "vertex_min",
    "vertex_max",
    "feasible_agents_num",
]


def feasible_agents_num_from_after_stats(stats: dict[str, Any]) -> int | str:
    """Число агентов с числом клиентских вершин в [vertex_min, vertex_max], без простаивающих."""
    if not stats.get("after_json_analyzed"):
        return ""
    try:
        n = int(stats["after_agents_in_file"])
        idle = int(stats["after_idle_agents"])
        bad = int(stats["after_vertex_bounds_violations"])
        return max(0, n - idle - bad)
    except (TypeError, ValueError):
        return ""


def summarize_tdtsp_after_json(
    after_path: Path,
    min_v: int,
    max_v: int,
    k_expected: int,
) -> dict[str, Any]:
    """
    Анализ *_after.json TDTSP-PD: число клиентских вершин на агента (v!=0).
    Пустой тур: [] или [0,0] после фикса в солвере — 0 клиентов.
    """
    empty = {
        "after_json_analyzed": False,
        "after_agents_in_file": "",
        "after_idle_agents": "",
        "after_vertex_bounds_violations": "",
        "after_all_agents_nonempty_client_routes": "",
        "after_all_agents_within_vertex_min_max": "",
        "after_iterative_launch_ok": "",
    }
    if not after_path.is_file():
        return empty
    try:
        with open(after_path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return empty

    agents = data.get("agents", [])
    n = len(agents)
    idle = 0
    bad_bounds = 0
    for a in agents:
        verts = a.get("vertexes")
        if not isinstance(verts, list):
            verts = []
        clients = sum(1 for v in verts if v != 0)
        if clients == 0:
            idle += 1
        elif clients < min_v or clients > max_v:
            bad_bounds += 1

    nonempty = idle == 0
    within = bad_bounds == 0 and idle == 0
    count_ok = n == k_expected
    struct_ok = nonempty and within and count_ok

    return {
        "after_json_analyzed": True,
        "after_agents_in_file": n,
        "after_idle_agents": idle,
        "after_vertex_bounds_violations": bad_bounds,
        "after_all_agents_nonempty_client_routes": nonempty,
        "after_all_agents_within_vertex_min_max": within,
        "after_iterative_launch_ok": struct_ok,
    }


def run_one(
    binary: Path,
    json_path: Path,
    timeout_sec: float | None,
) -> tuple[int, str, str, float]:
    t0 = time.perf_counter()
    try:
        r = subprocess.run(
            [str(binary), "-p", str(json_path.resolve()), "-t", "50"],
            capture_output=True,
            text=True,
            timeout=timeout_sec,
        )
        elapsed = time.perf_counter() - t0
        return r.returncode, r.stdout, r.stderr, elapsed
    except subprocess.TimeoutExpired as e:
        elapsed = time.perf_counter() - t0
        out = e.stdout or ""
        err = (e.stderr or "") + f"\n[timeout after {timeout_sec}s]\n"
        return -124, out, err, elapsed


def collect_instances_by_suffix(
    map_dir: Path,
    suffix: str,
) -> list[tuple[Path, float | None, str | None]]:
    """
    Возвращает список (json_path, p_from_parent_dir, p_tag_override) для файлов,
    оканчивающихся на заданный суффикс.
    Суффикс должен включать расширение .json, например '_tdtsp_base_demand_avg.json'.

    Подкаталог ``p_full`` (режим full-load-bounds в run_top_datasets.sh) даёт тег ``full``,
    как в scripts/run_ma_benchmark.py (не ``unknown``).
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
        for j in sorted(p.rglob(f"*{suffix}")):
            if j.is_file():
                out.append((j, p_val, p_tag_override))
    return out


def build_row(
    _map_name: str,
    json_path: Path,
    variant: str,
    data: dict[str, Any],
    parsed: dict[str, Any],
    _exit_code: int,
    _elapsed: float,
    _p_override: float | None,
    tdtsp_binary: str | None = None,
) -> dict[str, Any]:
    stem = json_path.stem
    n = int(data["points_count"])
    v_min = scalar_int(data, "min_load")
    v_max = scalar_int(data, "max_load")
    agents_cnt = int(data.get("agents_cnt") or data.get("agents_count") or 1)

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
    if tdtsp_binary is not None:
        row["tdtsp_binary"] = tdtsp_binary
    return row


def build_variant_suffix_pairs(variant: str, include_avg: bool) -> list[tuple[str, str]]:
    """
    Возвращает список пар (имя_варианта, суффикс_файла).
    Если include_avg == True, то только avg-версии.
    """
    base_suffixes = {
        "demand": "_tdtsp_base_demand.json",
        "unit": "_tdtsp_base_unit.json",
    }
    if variant == "both":
        base_names = ["demand", "unit"]
    else:
        base_names = [variant]

    pairs = []
    for bn in base_names:
        if include_avg:
            # только avg-версия
            avg_suffix = base_suffixes[bn].replace(".json", "_avg.json")
            pairs.append((f"{bn}_avg", avg_suffix))
        else:
            # только обычная версия
            pairs.append((bn, base_suffixes[bn]))
    return pairs


def main() -> int:
    root = repo_root_from_here()
    ap = argparse.ArgumentParser(
        description="Прогон TDTSP-PD по tdtsp_base JSON и CSV A_p10.csv по каждому p."
    )
    ap.add_argument(
        "--map",
        required=True,
        help="Имя набора (каталог под datasets-root), напр. A или CMT",
    )
    ap.add_argument(
        "--datasets-root",
        type=Path,
        default=root / "datasets" / "many",
        help="Родитель каталогов с картами (по умолчанию <repo>/datasets/many)",
    )
    ap.add_argument(
        "--output-dir",
        type=Path,
        default=root / "experiments" / "tdtsp_benchmark",
        help="Куда писать CSV",
    )
    ap.add_argument(
        "--binary",
        type=Path,
        default=None,
        help="Бинарник TDTSP-PD (иначе переменная окружения TDTSP_PD_BINARY)",
    )
    ap.add_argument(
        "--variant",
        choices=("demand", "unit", "both"),
        default="demand",
        help="Какие JSON гонять: demand / unit / оба",
    )
    ap.add_argument(
        "--avg",
        action="store_true",
        help="Дополнительно обрабатывать avg-версии файлов (*_tdtsp_base_*_avg.json)",
    )
    ap.add_argument(
        "--timeout",
        type=float,
        default=None,
        help="Таймаут секунд на один запуск (опционально)",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Только список файлов и пути CSV, без запуска бинарника",
    )
    ap.add_argument(
        "--write-binary-path",
        action="store_true",
        help="Добавить в каждую строку столбец tdtsp_binary (для воспроизводимости)",
    )
    args = ap.parse_args()

    ds = args.datasets_root.resolve()
    map_dir = ds / args.map
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
                    "Укажите --binary или задайте TDTSP_PD_BINARY на бинарник TDTSP-PD.",
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

    # Получаем список (имя_варианта, суффикс)
    variant_suffix_pairs = build_variant_suffix_pairs(args.variant, args.avg)

    # Группируем по p-тегу
    by_p_tag: dict[str, list[tuple[Path, str, float | None]]] = {}
    for vname, suffix in variant_suffix_pairs:
        for json_path, p_dir, p_tag_override in collect_instances_by_suffix(map_dir, suffix):
            base = instance_base_stem(json_path.stem)
            p_stem = extract_p_from_stem(base)
            p_use = p_dir if p_dir is not None else p_stem
            if p_tag_override is not None:
                tag = p_tag_override
            elif p_use is None:
                tag = "unknown"
            else:
                tag = p_to_filename_tag(float(p_use))
            by_p_tag.setdefault(tag, []).append((json_path, vname, p_use))

    if not by_p_tag:
        print(
            f"Нет инстансов с суффиксами {[s for _, s in variant_suffix_pairs]} под {map_dir}.\n"
            "Ожидаются подкаталоги p0.1, p0.2, … или p_full с JSON.",
            file=sys.stderr,
        )
        return 0 if args.dry_run else 1

    if args.dry_run:
        for tag, items in sorted(by_p_tag.items()):
            csv_path = out_dir / f"{args.map}_p{tag}.csv"
            print(f"{csv_path}  ({len(items)} instances)")
            for jp, vname, _ in items[:5]:
                print(f"  {vname}: {jp}")
            if len(items) > 5:
                print("  ...")
        return 0

    assert bin_path is not None

    for tag, items in sorted(by_p_tag.items()):
        csv_path = out_dir / f"{args.map}_p{tag}.csv"
        rows: list[dict[str, Any]] = []
        fieldnames = list(CSV_FIELDS)
        if args.write_binary_path:
            fieldnames.append("tdtsp_binary")

        for json_path, vname, p_use in sorted(items, key=lambda x: str(x[0])):
            data = load_instance(json_path)
            code, out, err, elapsed = run_one(bin_path, json_path, args.timeout)
            parsed = parse_tdtsp_stdout(out)
            if code != 0 and not parsed["per_agent_score"]:
                print(f"WARN exit={code} {json_path}\n{err[:500]}", file=sys.stderr)
            row = build_row(
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