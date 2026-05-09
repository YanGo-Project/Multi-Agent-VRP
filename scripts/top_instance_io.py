#!/usr/bin/env python3
"""
Общий разбор текстовых TOP-инстансов (как в top_datasets/*.txt).

Ожидаемый формат после необязательного баннера:
  n N
  m P
  tmax Tmax
  далее N строк: x y S  (пробелы или табуляция)

Режимы графа (аргумент depot_loop у parse_top_text):
  • depot_loop=False (по умолчанию): как в классических TOP-бенчмарках — первая точка старт,
    последняя отдельная «финишная» вершина (часто S=0).
  • depot_loop=True: одно депо (v=0), все маршруты начинаются и заканчиваются в нём; последняя
    строка файла считается лишней «фиктивной терминалью» и отбрасывается — в графе N−1 вершин.
"""
from __future__ import annotations

import math
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path


_TOP_BANNER_LINE = re.compile(r"^\s*[\*]+\s*$")
_TOP_TITLE_LINE = re.compile(r"^\s*\*\s*TOP\s+test\s+instances\s*\*\s*$", re.I)


@dataclass(frozen=True)
class TopInstance:
    n: int
    paths: int
    tmax: float
    xs: list[float]
    ys: list[float]
    scores: list[int]
    depot_loop: bool = False


def _strip_optional_banner(lines: list[str]) -> list[str]:
    """Убирает пустые строки и стандартный баннер TOP в начале файла."""
    i = 0
    while i < len(lines) and not lines[i].strip():
        i += 1
    # Баннер: строки из '*' и строка '* TOP test instances *'
    if i < len(lines) and _TOP_BANNER_LINE.match(lines[i]):
        j = i
        while j < len(lines) and (
            _TOP_BANNER_LINE.match(lines[j])
            or _TOP_TITLE_LINE.match(lines[j])
            or not lines[j].strip()
        ):
            j += 1
        # Если действительно похоже на баннер (минимум одна строка звёзд)
        if j > i:
            i = j
    while i < len(lines) and not lines[i].strip():
        i += 1
    return lines[i:]


def _parse_header(line: str, key: str) -> float:
    parts = line.split()
    if len(parts) < 2:
        raise ValueError(f"Строка заголовка '{line!r}': ожидалось '{key} <число>'")
    if parts[0].lower() != key.lower():
        raise ValueError(f"Ожидалась строка, начинающаяся с '{key}', получено: {line!r}")
    return float(parts[1]) if key == "tmax" else float(parts[1])


def parse_top_text(text: str, *, depot_loop: bool = False) -> TopInstance:
    raw_lines = text.splitlines()
    lines = _strip_optional_banner(raw_lines)
    if len(lines) < 3:
        raise ValueError("Слишком мало строк: нужны n, m, tmax и координаты")

    n_line = lines[0].split()
    m_line = lines[1].split()
    t_line = lines[2].split()
    if len(n_line) < 2 or n_line[0].lower() != "n":
        raise ValueError(f"Первая строка данных должна быть 'n N', получено: {lines[0]!r}")
    if len(m_line) < 2 or m_line[0].lower() != "m":
        raise ValueError(f"Вторая строка должна быть 'm P', получено: {lines[1]!r}")
    if len(t_line) < 2 or t_line[0].lower() != "tmax":
        raise ValueError(f"Третья строка должна быть 'tmax Tmax', получено: {lines[2]!r}")

    n = int(float(n_line[1]))
    m_paths = int(float(m_line[1]))
    tmax = float(t_line[1])

    rest = lines[3:]
    coords: list[tuple[float, float, int]] = []
    for ln in rest:
        s = ln.strip()
        if not s:
            continue
        parts = s.replace("\t", " ").split()
        if len(parts) < 3:
            raise ValueError(f"Строка точки должна быть 'x y S', получено: {ln!r}")
        x, y, sc = float(parts[0]), float(parts[1]), int(float(parts[2]))
        coords.append((x, y, sc))

    if len(coords) != n:
        raise ValueError(f"Ожидалось {n} точек, получено {len(coords)}")

    if depot_loop:
        if len(coords) < 2:
            raise ValueError("depot_loop: в файле должно быть минимум 2 строки координат")
        coords = coords[:-1]

    xs = [c[0] for c in coords]
    ys = [c[1] for c in coords]
    scores = [c[2] for c in coords]
    n_eff = len(coords)
    return TopInstance(
        n=n_eff,
        paths=m_paths,
        tmax=tmax,
        xs=xs,
        ys=ys,
        scores=scores,
        depot_loop=depot_loop,
    )


def parse_top_path(path: Path, *, depot_loop: bool = False) -> TopInstance:
    return parse_top_text(path.read_text(encoding="utf-8"), depot_loop=depot_loop)


def validate_endpoints(inst: TopInstance, *, strict: bool = False) -> list[str]:
    """Замечания по скорам старта (и финиша в бенчмарк-режиме без depot_loop)."""
    msgs: list[str] = []
    if inst.scores[0] != 0:
        msgs.append(f"первая точка (депо) имеет S={inst.scores[0]}, обычно 0")
    if not inst.depot_loop and len(inst.scores) > 1 and inst.scores[-1] != 0:
        msgs.append(f"последняя точка (терминал бенчмарка) имеет S={inst.scores[-1]}, часто 0")
    return msgs


TOP_BANNER = """**********************
* TOP test instances *
**********************"""


def format_top_normalized(inst: TopInstance) -> str:
    """Текст в каноническом виде с баннером (табуляция между x y S)."""
    lines = [
        TOP_BANNER,
        "",
        f"n {inst.n}",
        f"m {inst.paths}",
        f"tmax {_fmt_float(inst.tmax)}",
        "",
    ]
    for x, y, s in zip(inst.xs, inst.ys, inst.scores):
        lines.append(f"{_fmt_float(x)}\t{_fmt_float(y)}\t{s}")
    lines.append("")
    return "\n".join(lines)


def _fmt_float(v: float) -> str:
    if math.isfinite(v) and abs(v - round(v)) < 1e-9:
        return str(int(round(v)))
    return format(v, ".10g")


def euclidean_distance_matrix(
    xs: list[float],
    ys: list[float],
    *,
    round_fn: Callable[[float], int] | None = None,
) -> list[list[int]]:
    rf: Callable[[float], int] = round_fn if round_fn is not None else lambda z: int(round(z))
    n = len(xs)
    dist = [[0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            d = math.hypot(xs[i] - xs[j], ys[i] - ys[j])
            dist[i][j] = rf(d)
    return dist


def euclidean_distance_matrix_scaled(
    xs: list[float],
    ys: list[float],
    *,
    scale: float,
) -> list[list[int]]:
    """Целочисленные расстояния после умножения на scale (согласование с Tmax)."""

    def rf(x: float) -> int:
        return int(round(scale * x))

    n = len(xs)
    dist = [[0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            d = math.hypot(xs[i] - xs[j], ys[i] - ys[j])
            dist[i][j] = rf(d)
    return dist
