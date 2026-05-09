#!/usr/bin/env python3
"""
Преобразование TOP .txt → JSON для C++ алгоритма (TInputData).
Матрица расстояний и time_matrix — целочисленные.
"""

import argparse
import json
import math
import sys
from pathlib import Path
from typing import List, Tuple


def read_top_file(filepath: Path) -> Tuple[int, int, float, List[Tuple[float, float, int]]]:
    with open(filepath, 'r') as f:
        lines = [line.strip() for line in f if line.strip()]

    n_line = lines[0].split()
    assert n_line[0] == 'n'
    n = int(n_line[1])

    m_line = lines[1].split()
    assert m_line[0] == 'm'
    m = int(m_line[1])

    tmax_line = lines[2].split()
    assert tmax_line[0] == 'tmax'
    tmax = float(tmax_line[1])

    points = []
    for line in lines[3:3 + n]:
        parts = line.split()
        x = float(parts[0])
        y = float(parts[1])
        score = int(parts[2])
        points.append((x, y, score))

    if len(points) != n:
        raise ValueError(f"Ожидалось {n} точек, получено {len(points)}")
    return n, m, tmax, points


def distance_matrix_int(points: List[Tuple[float, float, int]], scale: float = 100.0) -> List[List[int]]:
    """Евклидова матрица расстояний, округлённая до целых."""
    n = len(points)
    mat = [[0] * n for _ in range(n)]
    for i in range(n):
        xi, yi, _ = points[i]
        for j in range(i + 1, n):
            xj, yj, _ = points[j]
            dx = xi - xj
            dy = yi - yj
            d = math.hypot(dx, dy) * scale
            # округление до ближайшего целого (можно int(d + 0.5) но round безопаснее)
            d_int = int(round(d))
            mat[i][j] = d_int
            mat[j][i] = d_int
    return mat


def determine_depots(points: List[Tuple[float, float, int]]) -> Tuple[int, int]:
    zero_indices = [i for i, (_, _, s) in enumerate(points) if s == 0]
    if not zero_indices:
        raise ValueError("Нет вершины с score 0 (депо).")
    start_depot = zero_indices[0]
    end_depot = zero_indices[-1] if len(zero_indices) > 1 else start_depot
    return start_depot, end_depot


def compute_load_bounds(num_clients: int, agents: int, balance_p: float) -> Tuple[int, int]:
    if agents <= 0:
        raise ValueError("agents_count должно быть положительным")
    avg = num_clients / agents
    min_load = max(1, math.floor(avg * (1 - balance_p)))
    max_load = max(min_load, math.ceil(avg * (1 + balance_p)))
    return min_load, max_load


def convert_top_to_json(input_file: Path, output_file: Path,
                        balance_p: float = 0.0,
                        scale: float = 100.0,
                        custom_min_load: int = None,
                        custom_max_load: int = None,
                        full_load_bounds: bool = False) -> None:
    n, m, tmax, points = read_top_file(input_file)

    start_depot, end_depot = determine_depots(points)

    point_scores = [int(round(score * scale)) for _, _, score in points]
    point_service_times = [0] * n

    dist_mat = distance_matrix_int(points, scale)

    num_clients = sum(1 for s in point_scores if s > 0)

    if full_load_bounds:
        min_load, max_load = 1, n
    elif custom_min_load is not None and custom_max_load is not None:
        min_load, max_load = custom_min_load, custom_max_load
    else:
        min_load, max_load = compute_load_bounds(num_clients, m, balance_p)

    # TOP-бюджет агента: ограничиваем и по времени, и по расстоянию реальным tmax.
    max_time = int(round(tmax * scale))
    max_distance = int(round(tmax * scale))

    depots = [start_depot] * m
    depots_end = [end_depot] * m
    agent_start_time = [0] * m  # целые

    data = {
        "points_count": n,
        "agents_count": m,
        "start_time": agent_start_time,
        "depots": depots,
        "depots_end": depots_end,
        "min_load": [min_load] * m,
        "max_load": [max_load] * m,
        "max_time": [max_time] * m,
        "max_distance": [max_distance] * m,
        "distance_matrix": dist_mat,
        "time_matrix": [dist_mat],      # один временной срез
        "point_scores": point_scores,
        "point_service_times": point_service_times
    }

    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"Сохранено: {output_file}")
    print(f"  вершин: {n}, агентов: {m}, клиентов: {num_clients}")
    print(f"  min_load={min_load}, max_load={max_load}, max_time={max_time}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--input", type=Path, required=True)
    parser.add_argument("-o", "--output", type=Path, required=True)
    parser.add_argument("--balance-p", type=float, default=0.0)
    parser.add_argument("--scale", type=float, default=100.0,
                        help="Масштабирование расстояний и времени (умножение, затем округление)")
    parser.add_argument("--min-load", type=int, default=None)
    parser.add_argument("--max-load", type=int, default=None)
    parser.add_argument(
        "--full-load-bounds",
        action="store_true",
        help="Принудительно min_load=1 и max_load=points_count.",
    )
    args = parser.parse_args()

    if not args.input.is_file():
        print(f"Ошибка: файл {args.input} не найден", file=sys.stderr)
        return 1

    if (args.min_load is None) != (args.max_load is None):
        print("Ошибка: --min-load и --max-load должны быть указаны оба", file=sys.stderr)
        return 1

    convert_top_to_json(
        input_file=args.input,
        output_file=args.output,
        balance_p=args.balance_p,
        scale=args.scale,
        custom_min_load=args.min_load,
        custom_max_load=args.max_load,
        full_load_bounds=args.full_load_bounds,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())