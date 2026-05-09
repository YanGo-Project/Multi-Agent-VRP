#!/usr/bin/env python3
"""
Конвертация TSPLIB CVRP (.vrp) → JSON для Multi-Agent-VRP и базового формата под TDTSP-PD.

Читает типичные секции: NAME, TYPE, DIMENSION, CAPACITY, EDGE_WEIGHT_TYPE,
NODE_COORD_SECTION, DEMAND_SECTION, DEPOT_SECTION; опционально EDGE_WEIGHT_SECTION
при EDGE_WEIGHT_TYPE: EXPLICIT и EDGE_WEIGHT_FORMAT: FULL_MATRIX / LOWER_ROW / LOWER_DIAG_ROW.

Склад в выходном JSON всегда depot_index=0: при необходимости матрица и спрос перенумерованы.

Расстояния для EUC_2D: округление до ближайшего целого (как в TSPLIB).
time_matrix: один слой, совпадающий с distance_matrix (статика).

Четыре выходных варианта (без --add-avg-to-scores):
  (1–2) Multi-Agent: agents_count=K, point_scores спросы / единицы
  (3–4) TDTSP base: agents_cnt=K, point_scores / point_service_times длины points_count − 1

При --add-avg-to-scores дополнительно создаются ещё четыре файла с суффиксом _avg,
в которых к каждому point_score (кроме депо) прибавлено среднее арифметическое
всех элементов distance_matrix (округлённое до целого).

K: VEHICLES / шаблон …-kN в имени; иначе соседний <stem>.sol (строки Route #).
С --prefer-sol-agents при наличии .sol K берётся из него в первую очередь.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path
from typing import Any

INT64_MAX = 9223372036854775807

_ROUTE_LINE_SOL = re.compile(r"^Route\s*#\s*\d+", re.IGNORECASE)


def stem_with_balance(base_stem: str, balance_p: float | None) -> str:
    if balance_p is None:
        return base_stem
    return f"{base_stem}_p{format(balance_p, 'g')}"


def infer_agents_from_vrp(meta: dict[str, Any], input_path: Path) -> tuple[int | None, str | None]:
    vehicle_keys = (
        "VEHICLES",
        "NUMBER_OF_VEHICLES",
        "NO_OF_VEHICLES",
        "NUM_VEHICLES",
        "VEHICLE_COUNT",
    )
    for vk in vehicle_keys:
        val = meta.get(vk)
        if isinstance(val, str) and val.strip():
            try:
                return int(val.strip().split()[0]), vk
            except ValueError:
                continue
    text_parts = [
        str(meta.get("NAME", "")),
        str(meta.get("COMMENT", "")),
        input_path.name,
        input_path.stem,
    ]
    blob = " ".join(text_parts)
    for pattern in (
        r"(?i)[_-]\s*k\s*(\d+)",
        r"(?i)\bn\s*\d+\s*[-_]?\s*k\s*(\d+)\b",
        r"(?i)\bk\s*[-_]?\s*(\d+)\s*(?:\.vrp)?\s*$",
    ):
        m = re.search(pattern, blob)
        if m:
            return int(m.group(1)), "NAME_OR_FILENAME_PATTERN"
    return None, None


def infer_agents_from_sol(sol_path: Path) -> tuple[int | None, str | None]:
    try:
        text = sol_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None, None
    n = 0
    for line in text.splitlines():
        s = line.strip()
        if s and _ROUTE_LINE_SOL.match(s):
            n += 1
    return (n, "SOL") if n > 0 else (None, None)


def euc_2d_distance(x1: float, y1: float, x2: float, y2: float) -> int:
    return int(round(math.hypot(x1 - x2, y1 - y2)))


def remap_depot_to_index_zero(
    dist: list[list[int]],
    demand_vec: list[int],
    depot_idx: int,
) -> tuple[list[list[int]], list[int], int]:
    n = len(dist)
    if depot_idx == 0:
        return dist, demand_vec, 0
    if not (0 <= depot_idx < n):
        raise ValueError(f"depot_idx вне диапазона: {depot_idx}, n={n}")
    d = depot_idx
    old_from_new = list(range(n))
    old_from_new[0] = d
    old_from_new[d] = 0
    new_dist = [[0] * n for _ in range(n)]
    for i in range(n):
        oi = old_from_new[i]
        row_oi = dist[oi]
        for j in range(n):
            new_dist[i][j] = row_oi[old_from_new[j]]
    new_demand = [demand_vec[old_from_new[j]] for j in range(n)]
    return new_dist, new_demand, 0


def parse_vrp(path: Path) -> dict[str, Any]:
    raw = path.read_text(encoding="utf-8", errors="replace")
    lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]

    meta_flat: dict[str, str] = {}
    section: str | None = None
    section_lines: list[str] = []

    def flush() -> None:
        nonlocal section, section_lines
        if section is None:
            return
        meta_flat[section] = section_lines[:]
        section_lines = []

    i = 0
    while i < len(lines):
        ln = lines[i]
        u = ln.upper()
        if u.endswith("_SECTION") or u in ("EOF",):
            flush()
            if u == "EOF":
                break
            section = ln.split()[0]
            if ":" in ln:
                rest = ln.split(":", 1)[1].strip()
                if rest:
                    section_lines.append(rest)
            i += 1
            continue
        if section:
            section_lines.append(ln)
        else:
            if ":" in ln:
                k, v = ln.split(":", 1)
                meta_flat[k.strip().upper()] = v.strip()
        i += 1
    flush()

    meta = meta_flat

    dimension = int(meta.get("DIMENSION", "0") or "0")
    capacity = int(meta.get("CAPACITY", "0") or "0")

    coords: dict[int, tuple[float, float]] = {}
    nc = meta.get("NODE_COORD_SECTION")
    if isinstance(nc, list):
        for row in nc:
            parts = row.split()
            if len(parts) >= 3:
                nid = int(parts[0])
                coords[nid] = (float(parts[1]), float(parts[2]))

    demands: dict[int, int] = {}
    ds = meta.get("DEMAND_SECTION")
    if isinstance(ds, list):
        for row in ds:
            parts = row.split()
            if len(parts) >= 2:
                nid = int(parts[0])
                demands[nid] = int(parts[1])

    depots: list[int] = []
    dsec_dep = meta.get("DEPOT_SECTION")
    if isinstance(dsec_dep, list):
        for row in dsec_dep:
            parts = row.split()
            for p in parts:
                v = int(p)
                if v == -1:
                    break
                depots.append(v)

    if not coords:
        raise ValueError("Пустая NODE_COORD_SECTION")

    sorted_old_ids = sorted(coords.keys())
    index_map: dict[int, int] = {old_id: idx for idx, old_id in enumerate(sorted_old_ids)}

    n = len(index_map)
    if dimension > 0 and dimension != n:
        print(
            f"Предупреждение: DIMENSION={dimension}, узлов с координатами={n}; используется n={n}.",
            file=sys.stderr,
        )
    if dimension <= 0:
        dimension = n

    edge_type = str(meta.get("EDGE_WEIGHT_TYPE", "EUC_2D")).upper()
    dist = [[0] * n for _ in range(n)]

    if edge_type == "EUC_2D":
        for i_old, i in index_map.items():
            xi, yi = coords[i_old]
            for j_old, j in index_map.items():
                if i <= j:
                    xj, yj = coords[j_old]
                    d = euc_2d_distance(xi, yi, xj, yj)
                    dist[i][j] = dist[j][i] = d
    elif edge_type == "EXPLICIT":
        fmt_raw = meta.get("EDGE_WEIGHT_FORMAT") or "FULL_MATRIX"
        fmt = str(fmt_raw).upper().strip()
        weights_flat: list[int] = []
        ew = meta.get("EDGE_WEIGHT_SECTION")
        if isinstance(ew, list):
            for row in ew:
                weights_flat.extend(int(x) for x in row.split())
        else:
            raise ValueError("EXPLICIT без EDGE_WEIGHT_SECTION не поддержан")

        if fmt == "FULL_MATRIX":
            expected = n * n
            if len(weights_flat) < expected:
                raise ValueError(
                    f"EDGE_WEIGHT_SECTION: ожидалось >= {expected} чисел, получено {len(weights_flat)}"
                )
            k = 0
            for i in range(n):
                for j in range(n):
                    dist[i][j] = weights_flat[k]
                    k += 1
        elif fmt in ("LOWER_DIAG_ROW", "LOWER_ROW"):
            k = 0
            for i in range(n):
                for j in range(i + 1):
                    if k >= len(weights_flat):
                        raise ValueError(f"{fmt}: не хватает весов")
                    dist[i][j] = dist[j][i] = weights_flat[k]
                    k += 1
        else:
            raise ValueError(f"EDGE_WEIGHT_FORMAT={fmt} не реализован")
    else:
        raise ValueError(f"EDGE_WEIGHT_TYPE={edge_type} не поддержан (ожидались EUC_2D или EXPLICIT)")

    # Вычисление среднего арифметического всех элементов матрицы (включая диагональ)
    total = 0
    count = n * n
    for row in dist:
        total += sum(row)
    avg_dist = total / count
    avg_dist_int = int(round(avg_dist))

    depot_old = depots[0] if depots else None
    if depot_old is None:
        for old_id in sorted(demands.keys()):
            if demands.get(old_id, 0) == 0:
                depot_old = old_id
                break
    if depot_old is None:
        depot_old = min(coords.keys())

    depot_idx = index_map[depot_old]

    demand_vec = [0] * n
    for old_id, idx in index_map.items():
        demand_vec[idx] = int(demands.get(old_id, 0))

    depot_before = depot_idx
    dist, demand_vec, depot_idx = remap_depot_to_index_zero(dist, demand_vec, depot_idx)
    if depot_before != 0:
        print(
            f"Примечание: склад в промежуточной нумерации имел индекс {depot_before}; "
            "матрица и спрос перенумерованы, в JSON depot_index=0.",
            file=sys.stderr,
        )

    vrp_meta: dict[str, Any] = dict(meta)

    return {
        "n": n,
        "capacity": capacity,
        "depot_index": depot_idx,
        "distance_matrix": dist,
        "demand_vec": demand_vec,
        "edge_weight_type": edge_type,
        "vrp_meta": vrp_meta,
        "avg_distance_int": avg_dist_int,   # новое поле
    }


def effective_capacity(capacity: int, n: int) -> int:
    if capacity > 0:
        return capacity
    print(
        "Предупреждение: CAPACITY отсутствует или 0; для max_load используется n-1.",
        file=sys.stderr,
    )
    return max(1, n - 1)


def big_limits(dist: list[list[int]]) -> tuple[int, int]:
    mx = 0
    for row in dist:
        mx = max(mx, max(row))
    n = len(dist)
    cap = mx * max(n, 2) * 100
    return cap, cap


def route_limits(dist: list[list[int]], huge: bool) -> tuple[int, int]:
    if huge:
        return INT64_MAX, INT64_MAX
    return big_limits(dist)


def vertex_load_bounds_from_p(
    num_clients: int,
    k_agents: int,
    p: float,
    cap_limit: int,
    policy: str,
) -> tuple[int, int, dict[str, Any]]:
    if k_agents <= 0:
        raise ValueError("K (число агентов) должно быть > 0")
    if num_clients < 0:
        raise ValueError("|C| не может быть отрицательным")
    if not (0.0 <= p < 1.0):
        raise ValueError("p должно быть в [0, 1)")

    c = int(num_clients)
    k = int(k_agents)
    mu = c / k
    min_raw = mu * (1.0 - p)
    max_raw = mu * (1.0 + p)
    min_v = max(0, int(math.floor(min_raw)))
    max_v = int(math.ceil(max_raw))
    cap_clamped = min(int(cap_limit), c)
    max_v = min(max_v, cap_clamped)
    if min_v > max_v:
        if policy == "relax":
            max_v = min_v
        else:
            raise ValueError(
                f"После обрезки max к Q=|C|: min={min_v} > max={max_v}. "
                "Увеличьте p или проверьте Q и K."
            )

    sum_min = k * min_v
    sum_max = k * max_v
    ok_lo = sum_min <= c
    ok_hi = sum_max >= c
    adjusted = False

    if not (ok_lo and ok_hi):
        if policy == "strict":
            raise ValueError(
                f"Нарушение разрешимости при p={p}: |C|={c}, K={k}, min={min_v}, max={max_v}. "
                "Попробуйте другой p, K или --balance-policy relax."
            )
        while k * min_v > c and min_v > 0:
            min_v -= 1
            adjusted = True
        while k * max_v < c and max_v < cap_clamped:
            max_v += 1
            adjusted = True
        max_v = max(max_v, min_v)
        if k * min_v > c or k * max_v < c:
            raise ValueError(
                f"Даже после relax: |C|={c}, K={k}, min={min_v}, max={max_v}. "
                "Увеличьте CAPACITY в .vrp, p или K."
            )

    report: dict[str, Any] = {
        "num_clients_C": c,
        "K": k,
        "p": p,
        "mu": mu,
        "min_raw": min_raw,
        "max_raw": max_raw,
        "min_load": min_v,
        "max_load": max_v,
        "floor_min": int(math.floor(min_raw)),
        "ceil_max_unclipped": int(math.ceil(max_raw)),
        "cap_clamped": cap_clamped,
        "check_K_min_le_C": (k * min_v <= c),
        "check_C_le_K_max": (c <= k * max_v),
        "K_times_min": k * min_v,
        "K_times_max": k * max_v,
        "adjusted": adjusted,
    }
    report["min_load"] = min_v
    report["max_load"] = max_v
    report["K_times_min"] = k * min_v
    report["K_times_max"] = k * max_v
    report["check_K_min_le_C"] = k * min_v <= c
    report["check_C_le_K_max"] = c <= k * max_v
    return min_v, max_v, report


def print_balance_report(rep: dict[str, Any]) -> None:
    print("\n=== Балансировка min/max вершин (параметр p) ===", file=sys.stderr)
    print(
        f"  |C| = {rep['num_clients_C']},  K = {rep['K']},  p = {rep['p']}",
        file=sys.stderr,
    )
    print(f"  μ = |C|/K = {rep['mu']:.10g}", file=sys.stderr)
    print(
        f"  min_raw = μ·(1−p) = {rep['min_raw']:.10g}  →  min_load = {rep['min_load']}",
        file=sys.stderr,
    )
    print(
        f"  max_raw = μ·(1+p) = {rep['max_raw']:.10g}  →  max_load = {rep['max_load']}",
        file=sys.stderr,
    )
    ok = rep["check_K_min_le_C"] and rep["check_C_le_K_max"]
    print(
        f"  Проверка: K·min ≤ |C| ≤ K·max  →  {'OK' if ok else 'FAIL'}",
        file=sys.stderr,
    )
    if rep.get("adjusted"):
        print("  Режим relax подправил min/max.", file=sys.stderr)


def build_point_scores(
    demand_vec: list[int], depot_index: int, unit_scores: bool, add_avg: int = 0
) -> list[int]:
    out = [0] * len(demand_vec)
    for i in range(len(demand_vec)):
        if i == depot_index:
            out[i] = 0
        else:
            base = 1 if unit_scores else int(demand_vec[i])
            out[i] = base + add_avg
    return out


def build_tdtsp_point_scores_and_service(
    demand_vec: list[int], depot_index: int, unit_scores: bool, add_avg: int = 0, scale : int = 1
) -> tuple[list[int], list[int]]:
    n = len(demand_vec)
    scores: list[int] = []
    service: list[int] = []
    for v in range(1, n):
        if v == depot_index:
            scores.append(0)
        else:
            base = (1 if unit_scores else int(demand_vec[v])) * scale
            scores.append(base + add_avg)
        service.append(0)
    return scores, service


def emit_multi_agent(
    parsed: dict[str, Any],
    agents: int,
    unit_scores: bool,
    out_path: Path,
    vertex_bounds: tuple[int, int] | None = None,
    huge_limits: bool = False,
    add_avg: int = 0,
) -> None:
    n = parsed["n"]
    dist = parsed["distance_matrix"]
    depot = parsed["depot_index"]
    demand_vec = parsed["demand_vec"]
    cap = effective_capacity(parsed["capacity"], n)

    mt, md = route_limits(dist, huge_limits)
    scores = build_point_scores(demand_vec, depot, unit_scores, add_avg)
    service = [0] * n
    tm = [dist]

    if vertex_bounds is not None:
        min_v, max_v = vertex_bounds
        min_row = [min_v] * agents
        max_row = [max_v] * agents
    else:
        min_row = [0] * agents
        max_row = [min(cap, max(1, n - 1))] * agents

    data = {
        "points_count": n,
        "agents_count": agents,
        "start_time": [0] * agents,
        "depots": [depot] * agents,
        "min_load": min_row,
        "max_load": max_row,
        "max_time": [mt] * agents,
        "max_distance": [md] * agents,
        "distance_matrix": dist,
        "time_matrix": tm,
        "point_scores": scores,
        "point_service_times": service,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(out_path)


def emit_tdtsp_base(
    parsed: dict[str, Any],
    unit_scores: bool,
    out_path: Path,
    min_load_tdtsp: int,
    agents_k: int,
    vertex_bounds: tuple[int, int] | None = None,
    huge_limits: bool = False,
    add_avg: int = 0,
) -> None:
    n = parsed["n"]
    dist = parsed["distance_matrix"]
    depot = parsed["depot_index"]
    demand_vec = parsed["demand_vec"]
    cap = effective_capacity(parsed["capacity"], n)

    mt, md = route_limits(dist, huge_limits)
    scores, service = build_tdtsp_point_scores_and_service(
        demand_vec, depot, unit_scores, add_avg
    )
    tm = [dist]

    if vertex_bounds is not None:
        min_v, max_v = vertex_bounds
        ml = max(1, min_v)
        mxl = max_v
        if ml != min_v:
            print(
                f"Предупреждение (TDTSP base): min было {min_v}, поднято до min_load={ml}.",
                file=sys.stderr,
            )
    else:
        ml = max(1, min_load_tdtsp)
        mxl = min(cap, max(1, n - 1))

    data = {
        "agents_cnt": agents_k,
        "points_count": n,
        "min_load": ml,
        "max_load": mxl,
        "max_time": mt,
        "max_distance": md,
        "distance_matrix": dist,
        "time_matrix": tm,
        "point_scores": scores,
        "point_service_times": service,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(out_path)


def convert_vrp_to_four_jsons(
    input_vrp: Path,
    out_dir: Path,
    *,
    stem: str | None = None,
    agents: int | None = None,
    min_load_tdtsp: int = 1,
    balance_p: float | None = None,
    balance_policy: str = "strict",
    balance_report: Path | None = None,
    huge_limits: bool = False,
    prefer_sol_agents: bool = False,
    add_avg_to_scores: bool = False,
) -> int:
    stem = stem or input_vrp.stem
    out_stem = stem_with_balance(stem, balance_p)

    parsed = parse_vrp(input_vrp)
    vrp_meta = parsed["vrp_meta"]
    avg_dist_int = parsed["avg_distance_int"]

    inferred_k, inferred_src = infer_agents_from_vrp(vrp_meta, input_vrp)

    sol_path = input_vrp.with_suffix(".sol")
    k_sol: int | None = None
    if sol_path.is_file():
        k_sol, _ = infer_agents_from_sol(sol_path)

    if agents is not None:
        agents_k = agents
        agents_src = "CLI"
        if inferred_k is not None and inferred_k != agents_k:
            print(
                f"Замечание: в .vrp K={inferred_k} ({inferred_src}), используется K={agents_k} из --agents.",
                file=sys.stderr,
            )
    else:
        if prefer_sol_agents and k_sol is not None:
            agents_k = k_sol
            agents_src = "SOL"
            if inferred_k is not None and inferred_k != agents_k:
                print(
                    f"Замечание: в .vrp K={inferred_k}, в {sol_path.name} K={k_sol}; берём .sol.",
                    file=sys.stderr,
                )
        elif inferred_k is not None:
            agents_k = inferred_k
            agents_src = inferred_src or "FILE"
        elif k_sol is not None:
            agents_k = k_sol
            agents_src = "SOL"
        else:
            print(
                "Ошибка: не удалось определить K. Добавьте VEHICLES, имя …-kN, <stem>.sol или --agents K",
                file=sys.stderr,
            )
            return 1

    print(f"Число агентов K={agents_k} (источник: {agents_src})", file=sys.stderr)

    parsed.pop("vrp_meta", None)

    n = parsed["n"]
    mem_gb = (n * n * 8 * 2) / (1024**3)
    if mem_gb > 2:
        print(
            f"Предупреждение: n={n}, память под матрицы ~{mem_gb:.1f} GiB.",
            file=sys.stderr,
        )

    vertex_bounds: tuple[int, int] | None = None
    if balance_p is not None:
        cap_eff = effective_capacity(parsed["capacity"], n)
        num_clients = n - 1
        try:
            min_v, max_v, balance_rep = vertex_load_bounds_from_p(
                num_clients,
                agents_k,
                balance_p,
                cap_eff,
                balance_policy,
            )
        except ValueError as e:
            print(f"Ошибка: {e}", file=sys.stderr)
            return 1
        vertex_bounds = (min_v, max_v)
        print_balance_report(balance_rep)
        if balance_report is not None:
            balance_report.parent.mkdir(parents=True, exist_ok=True)
            with open(balance_report, "w", encoding="utf-8") as bf:
                json.dump(balance_rep, bf, ensure_ascii=False, indent=2)
            print(f"Отчёт: {balance_report}", file=sys.stderr)

    od = out_dir

    # Базовые 4 файла (без добавки среднего)
    emit_multi_agent(
        parsed,
        agents_k,
        unit_scores=False,
        out_path=od / f"{out_stem}_ma_demand_K{agents_k}.json",
        vertex_bounds=vertex_bounds,
        huge_limits=huge_limits,
        add_avg=0,
    )
    emit_multi_agent(
        parsed,
        agents_k,
        unit_scores=True,
        out_path=od / f"{out_stem}_ma_unit_K{agents_k}.json",
        vertex_bounds=vertex_bounds,
        huge_limits=huge_limits,
        add_avg=0,
    )
    emit_tdtsp_base(
        parsed,
        unit_scores=False,
        out_path=od / f"{out_stem}_tdtsp_base_demand.json",
        min_load_tdtsp=min_load_tdtsp,
        agents_k=agents_k,
        vertex_bounds=vertex_bounds,
        huge_limits=huge_limits,
        add_avg=0,
    )
    emit_tdtsp_base(
        parsed,
        unit_scores=True,
        out_path=od / f"{out_stem}_tdtsp_base_unit.json",
        min_load_tdtsp=min_load_tdtsp,
        agents_k=agents_k,
        vertex_bounds=vertex_bounds,
        huge_limits=huge_limits,
        add_avg=0,
    )

    # Дополнительные 4 файла с добавкой среднего расстояния (если флаг установлен)
    if add_avg_to_scores and avg_dist_int != 0:
        print(f"Добавляем к point_scores значение avg_dist = {avg_dist_int}", file=sys.stderr)
        emit_multi_agent(
            parsed,
            agents_k,
            unit_scores=False,
            out_path=od / f"{out_stem}_ma_demand_avg_K{agents_k}.json",
            vertex_bounds=vertex_bounds,
            huge_limits=huge_limits,
            add_avg=avg_dist_int,
        )
        emit_multi_agent(
            parsed,
            agents_k,
            unit_scores=True,
            out_path=od / f"{out_stem}_ma_unit_avg_K{agents_k}.json",
            vertex_bounds=vertex_bounds,
            huge_limits=huge_limits,
            add_avg=avg_dist_int,
        )
        emit_tdtsp_base(
            parsed,
            unit_scores=False,
            out_path=od / f"{out_stem}_tdtsp_base_demand_avg.json",
            min_load_tdtsp=min_load_tdtsp,
            agents_k=agents_k,
            vertex_bounds=vertex_bounds,
            huge_limits=huge_limits,
            add_avg=avg_dist_int,
        )
        emit_tdtsp_base(
            parsed,
            unit_scores=True,
            out_path=od / f"{out_stem}_tdtsp_base_unit_avg.json",
            min_load_tdtsp=min_load_tdtsp,
            agents_k=agents_k,
            vertex_bounds=vertex_bounds,
            huge_limits=huge_limits,
            add_avg=avg_dist_int,
        )
    elif add_avg_to_scores and avg_dist_int == 0:
        print("Предупреждение: avg_distance_int = 0, дополнительные файлы не созданы.", file=sys.stderr)

    print(
        f"\nГотово. prepare_tdtsp: python3 scripts/prepare_tdtsp_instances.py -i "
        f"{od}/{out_stem}_tdtsp_base_demand.json -o <dir> --k-feasible-max-range\n",
        file=sys.stderr,
    )
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Конвертация .vrp (TSPLIB CVRP) в JSON (Multi-Agent и база TDTSP-PD)."
    )
    ap.add_argument("-i", "--input", type=Path, required=True, help="Путь к .vrp")
    ap.add_argument(
        "-o",
        "--out-dir",
        type=Path,
        default=Path("experiments/cvrplib_json"),
        help="Каталог для четырёх JSON",
    )
    ap.add_argument(
        "--agents",
        "-K",
        type=int,
        default=None,
        metavar="K",
        help="Число агентов (иначе из .vrp / .sol / имени)",
    )
    ap.add_argument("--stem", type=str, default="", help="Префикс имён файлов")
    ap.add_argument(
        "--min-load-tdtsp",
        type=int,
        default=1,
        help="min_load для tdtsp_base без --balance-p",
    )
    ap.add_argument("--balance-p", type=float, default=None, metavar="P")
    ap.add_argument(
        "--balance-policy",
        choices=("strict", "relax"),
        default="strict",
    )
    ap.add_argument("--balance-report", type=Path, default=None)
    ap.add_argument(
        "--huge-limits",
        action="store_true",
        help="max_time/max_distance = 2^63-1",
    )
    ap.add_argument(
        "--prefer-sol-agents",
        action="store_true",
        help="Предпочитать K из соседнего <stem>.sol",
    )
    ap.add_argument(
        "--add-avg-to-scores",
        action="store_true",
        help="Добавить к point_scores (кроме депо) среднее арифметическое матрицы расстояний (округлённое до целого). Создаются дополнительные *_avg.json файлы.",
    )
    args = ap.parse_args()

    stem = args.stem or args.input.stem
    br = args.balance_report
    if br is None and args.balance_p is not None:
        br = args.out_dir / f"{stem_with_balance(stem, args.balance_p)}_balance_report.json"

    return convert_vrp_to_four_jsons(
        args.input,
        args.out_dir,
        stem=stem,
        agents=args.agents,
        min_load_tdtsp=args.min_load_tdtsp,
        balance_p=args.balance_p,
        balance_policy=args.balance_policy,
        balance_report=br if args.balance_p is not None else None,
        huge_limits=args.huge_limits,
        prefer_sol_agents=args.prefer_sol_agents,
        add_avg_to_scores=args.add_avg_to_scores,
    )


if __name__ == "__main__":
    raise SystemExit(main())