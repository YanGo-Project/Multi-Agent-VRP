#!/usr/bin/env python3
"""
TOP .txt → четыре JSON:

  <stem>_ma_demand_K<m>.json, <stem>_ma_unit_K<m>.json,
  <stem>_tdtsp_base_demand.json, <stem>_tdtsp_base_unit.json

where m is the number of routes from TOP header "m P" (same m in agents_cnt/agents_count
for both ma_* and tdtsp_base_* files).

All generated JSONs are aligned with `TInputData` parser keys:
`agents_count`, `start_time`, `depots`, `depots_end`,
`min_load`, `max_load`, `max_time`, `max_distance`.

By default, the benchmark-style start/end depots are preserved
(`start=0`, `end=n-1`). Use `--depot-loop` to collapse into one depot.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path


def main() -> int:
    repo = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo / "scripts"))
    from cvrplib_vrp_to_json import effective_capacity, stem_with_balance, vertex_load_bounds_from_p
    from top_instance_io import euclidean_distance_matrix_scaled, parse_top_path  # noqa: E402

    ap = argparse.ArgumentParser(
        description="TOP txt → ma_* + tdtsp_base_* JSON (как build_dataset_json для .vrp)"
    )
    ap.add_argument("-i", "--input", type=Path, required=True, help="Файл TOP .txt")
    ap.add_argument(
        "-o",
        "--out-dir",
        type=Path,
        required=True,
        help="Каталог для записи JSON",
    )
    ap.add_argument(
        "--scale",
        type=float,
        default=1000.0,
        help="Общий множитель для расстояний/времени/ограничений/score (по умолчанию 1000)",
    )
    ap.add_argument(
        "--balance-p",
        type=float,
        default=None,
        metavar="P",
        help="Как в build_dataset_json: полоса ± вокруг μ=|C|/K для min_load/max_load",
    )
    ap.add_argument(
        "--balance-policy",
        choices=("strict", "relax"),
        default="strict",
    )
    ap.add_argument(
        "--min-load-tdtsp",
        type=int,
        default=1,
        help="Базовый min_load, если не задан --balance-p",
    )
    ap.add_argument(
        "--stem-prefix",
        type=str,
        default="",
        help="Префикс имени выходных файлов (например p_full_)",
    )
    ap.add_argument(
        "--stem-suffix",
        type=str,
        default="",
        help="Дописать к имени выходных файлов (например _p01)",
    )
    ap.add_argument(
        "--variant",
        choices=("demand", "both"),
        default="both",
        help="Какие JSON писать: только demand или demand+unit (по умолчанию both)",
    )
    ap.add_argument(
        "--full-load-bounds",
        action="store_true",
        help="Принудительно: min_load=1, max_load=points_count для каждого агента.",
    )
    ap.add_argument(
        "--keep-last-vertex",
        action="store_true",
        help="Совместимость со старым CLI; эквивалент поведения по умолчанию (сохраняет отдельный конечный депо).",
    )
    ap.add_argument(
        "--depot-loop",
        action="store_true",
        help="Один депо: отбросить последнюю строку координат и сделать depots_end == depots.",
    )
    args = ap.parse_args()

    src = args.input.resolve()
    if not src.is_file():
        print(f"Нет файла: {src}", file=sys.stderr)
        return 1

    if args.depot_loop and args.keep_last_vertex:
        print("Нельзя одновременно использовать --depot-loop и --keep-last-vertex", file=sys.stderr)
        return 1

    inst = parse_top_path(src, depot_loop=args.depot_loop)
    scale = float(args.scale)
    if not math.isfinite(scale) or scale <= 0:
        print("--scale должен быть конечным и > 0", file=sys.stderr)
        return 1

    dist = euclidean_distance_matrix_scaled(inst.xs, inst.ys, scale=scale)
    demand_vec = [int(s) for s in inst.scores]
    n = inst.n
    start_depot = 0
    end_depot = 0 if args.depot_loop else (n - 1)
    depot_index = start_depot

    demand_sum = sum(demand_vec)
    parsed_capacity = demand_sum if demand_sum > 0 else max(1, n - 1)
    parsed = {
        "n": n,
        "capacity": parsed_capacity,
        "depot_index": depot_index,
        "distance_matrix": dist,
        "demand_vec": demand_vec,
    }

    cap_raw = max(1, sum(1 for d in demand_vec if d > 0))
    capacity_balance = max(cap_raw, n - 2)
    cap_eff = effective_capacity(capacity_balance, n)

    num_clients = sum(1 for i in range(n) if demand_vec[i] > 0)

    vertex_bounds_ma: tuple[int, int] | None = None
    if args.full_load_bounds:
        vertex_bounds_ma = (1, n)
        ml = 1
        mxl = n
    else:
        if args.balance_p is not None:
            min_v, max_v, _rep = vertex_load_bounds_from_p(
                num_clients,
                inst.paths,
                args.balance_p,
                cap_limit=min(cap_eff, num_clients if num_clients > 0 else n),
                policy=args.balance_policy,
            )
            vertex_bounds_ma = (min_v, max_v)
            ml = max(1, min_v)
            mxl = max(ml, max_v)
        else:
            ml = max(1, args.min_load_tdtsp)
            mxl = min(cap_eff, max(1, n - 1))

    base_stem = args.stem_prefix + src.stem + args.stem_suffix
    out_stem = stem_with_balance(base_stem, args.balance_p)
    od = args.out_dir.resolve()
    od.mkdir(parents=True, exist_ok=True)

    mt = int(round(scale * inst.tmax))
    md = int(round(scale * inst.tmax))

    def scaled_score(v: int) -> int:
        return int(round(v * scale))

    def emit_common(
        *,
        suffix: str,
        agents_count: int,
        min_row: list[int],
        max_row: list[int],
        point_scores: list[int],
    ) -> None:
        start_time = [0] * agents_count
        depots = [start_depot] * agents_count
        depots_end = [end_depot] * agents_count
        data = {
            "agents_cnt": agents_count,  # back-compat for benchmark readers
            "points_count": n,
            "agents_count": agents_count,
            "start_time": start_time,
            "depots": depots,
            "depots_end": depots_end,
            "min_load": min_row,
            "max_load": max_row,
            "max_time": [mt] * agents_count,
            "max_distance": [md] * agents_count,
            "distance_matrix": dist,
            "time_matrix": [dist],
            "point_scores": point_scores,
            "point_service_times": [0] * n,
        }
        outp = od / suffix
        with open(outp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(outp)

    if vertex_bounds_ma is not None:
        min_v, max_v = vertex_bounds_ma
        ma_min_row = [min_v] * inst.paths
        ma_max_row = [max_v] * inst.paths
    else:
        ma_min_row = [0] * inst.paths
        ma_max_row = [min(cap_eff, max(1, n - 1))] * inst.paths

    demand_scores = [0 if i in (start_depot, end_depot) else scaled_score(int(demand_vec[i])) for i in range(n)]
    unit_scores = [0 if i in (start_depot, end_depot) else scaled_score(1) for i in range(n)]

    emit_common(
        suffix=f"{out_stem}_ma_demand_K{inst.paths}.json",
        agents_count=inst.paths,
        min_row=ma_min_row,
        max_row=ma_max_row,
        point_scores=demand_scores,
    )
    if args.variant == "both":
        emit_common(
            suffix=f"{out_stem}_ma_unit_K{inst.paths}.json",
            agents_count=inst.paths,
            min_row=ma_min_row,
            max_row=ma_max_row,
            point_scores=unit_scores,
        )

    # Как в строке TOP «m P»: столько же агентов в JSON (TDTSP-PD крутит agents_cnt итераций;
    # бенчмарки читают agents_count для сверки с TOP).
    tdtsp_k = inst.paths
    tdtsp_min = [ml] * tdtsp_k
    tdtsp_max = [mxl] * tdtsp_k
    emit_common(
        suffix=f"{out_stem}_tdtsp_base_demand.json",
        agents_count=tdtsp_k,
        min_row=tdtsp_min,
        max_row=tdtsp_max,
        point_scores=demand_scores,
    )
    if args.variant == "both":
        emit_common(
            suffix=f"{out_stem}_tdtsp_base_unit.json",
            agents_count=tdtsp_k,
            min_row=tdtsp_min,
            max_row=tdtsp_max,
            point_scores=unit_scores,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
