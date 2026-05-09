#!/usr/bin/env python3
"""
Визуализация TOP-инстансов (текст после normalize_top_txt / top_datasets) и маршрутов решения.

Формат входного .txt: баннер опционален; далее n N, m P, tmax Tmax и N строк x y S.
Индексы вершин 0 … N−1 как в JSON солвера.
По умолчанию: start_depot=v0, end_depot=v(N-1); в --depot-loop это одна и та же вершина.

Маршруты (опционально): JSON с ключом \"agents\", как у utils/draw.py / выхода TDTSP-PD:
  {\"agents\": [{\"vertexes\": [0, 3, 5, …]}, …]}

Запуск как у utils/draw.py (вторая карта — TOP-текст вместо .vrp):
  python utils/draw_top.py input.txt agents.json

Только точки инстанса (один аргумент):
  python utils/draw_top.py input.txt

Сохранить файл без окна (доп. флаги):
  python utils/draw_top.py input.txt agents.json -o fig.png --no-show

Один депо в данных (убрать последнюю строку файла из графа):
  python utils/draw_top.py --depot-loop input.txt agents.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "scripts"))

from top_instance_io import TopInstance, parse_top_path  # noqa: E402

_UTILS_DIR = Path(__file__).resolve().parent
if str(_UTILS_DIR) not in sys.path:
    sys.path.insert(0, str(_UTILS_DIR))

import draw as draw_vrp  # noqa: E402


def _load_agents(path: Path | None) -> list[dict] | None:
    if path is None:
        return None
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    agents = data.get("agents")
    if not isinstance(agents, list):
        raise ValueError("JSON: ожидался ключ 'agents' со списком")
    return agents


def _dedupe_consecutive(route: list) -> list[int]:
    """Убирает подряд идущие одинаковые вершины (артефакты солвера)."""
    out: list[int] = []
    for v in route:
        iv = int(v)
        if not out or out[-1] != iv:
            out.append(iv)
    return out


def _start_end_depots(inst: TopInstance) -> tuple[int, int]:
    start_depot = 0
    end_depot = 0 if inst.depot_loop else (inst.n - 1)
    return start_depot, end_depot


def _depots_coincide(inst: TopInstance, start_depot: int, end_depot: int) -> bool:
    if start_depot == end_depot:
        return True
    return (
        float(inst.xs[start_depot]) == float(inst.xs[end_depot])
        and float(inst.ys[start_depot]) == float(inst.ys[end_depot])
    )


def draw_top_points_only(ax, inst: TopInstance, *, title: str | None) -> None:
    """Только точки: цвет/размер по S; старт/финиш депо выделены отдельно."""
    xs = np.array(inst.xs, dtype=float)
    ys = np.array(inst.ys, dtype=float)
    scores = np.array(inst.scores, dtype=float)
    start_depot, end_depot = _start_end_depots(inst)

    positive = scores > 0
    if positive.any():
        sz = 25.0 + 0.45 * np.clip(scores, 0.0, None)
        sc = ax.scatter(
            xs[positive],
            ys[positive],
            c=scores[positive],
            cmap="viridis",
            s=sz[positive],
            alpha=0.92,
            edgecolors="black",
            linewidths=0.35,
            zorder=2,
            label="score > 0",
        )
        plt.colorbar(sc, ax=ax, fraction=0.046, pad=0.04, label="S")

    zero_idx = ~positive
    if zero_idx.any():
        ax.scatter(
            xs[zero_idx],
            ys[zero_idx],
            s=55,
            c="lightgray",
            edgecolors="dimgray",
            linewidths=0.6,
            zorder=1,
            label="S = 0",
        )

    depots_same = _depots_coincide(inst, start_depot, end_depot)
    ax.scatter(
        [xs[start_depot]],
        [ys[start_depot]],
        s=220,
        marker="s",
        c="limegreen",
        edgecolors="black",
        linewidths=1.2,
        zorder=5,
        label=(
            f"start/end depot (v={start_depot})"
            if depots_same
            else f"start depot (v={start_depot})"
        ),
    )
    if not depots_same:
        ax.scatter(
            [xs[end_depot]],
            [ys[end_depot]],
            s=220,
            marker="D",
            c="tomato",
            edgecolors="black",
            linewidths=1.2,
            zorder=5,
            label=f"end depot (v={end_depot})",
        )

    ax.set_aspect("equal", adjustable="datalim")
    ax.set_xticks([])
    ax.set_yticks([])
    ax.grid(False)
    ttl = title or "TOP instance"
    ax.set_title(ttl)
    ax.legend(loc="center left", bbox_to_anchor=(1.02, 0.5), fontsize=9)


def draw_top_with_routes(
    ax,
    inst: TopInstance,
    agents: list[dict],
    *,
    title: str | None,
) -> None:
    """Маршруты поверх карты (как utils/draw.py): посещённые / не посещённые вершины."""
    n = inst.n
    start_depot, end_depot = _start_end_depots(inst)
    coords = {i + 1: (inst.xs[i], inst.ys[i]) for i in range(n)}
    colors = draw_vrp._colors_for_n_agents(len(agents))
    visited: set[int] = set()
    NODE_SIZE = 42
    # Маркер на каждую внутреннюю вершину один раз; депо рисуем отдельными маркерами.
    scatter_drawn: set[int] = set()

    for i, agent in enumerate(agents):
        route = agent.get("vertexes")
        if not isinstance(route, list):
            continue
        seq = _dedupe_consecutive(route)
        xs: list[float] = []
        ys: list[float] = []
        vx: list[float] = []
        vy: list[float] = []
        for v in seq:
            vs = int(v)
            vid = vs + 1
            visited.add(vid)
            x, y = coords[vid]
            xs.append(x)
            ys.append(y)
            if vs in (start_depot, end_depot):
                continue
            if vs in scatter_drawn:
                continue
            scatter_drawn.add(vs)
            vx.append(x)
            vy.append(y)

        if len(xs) < 2:
            continue
        lbl = f"agent {agent.get('index', i)}"
        ax.plot(
            xs,
            ys,
            color=colors[i],
            linewidth=2.5,
            solid_capstyle="round",
            alpha=0.9,
            zorder=2,
            label=lbl,
        )
        if vx:
            ax.scatter(
                vx,
                vy,
                s=NODE_SIZE,
                color=colors[i],
                edgecolors="black",
                linewidths=0.5,
                zorder=3,
            )

    all_nodes = set(range(1, n + 1))
    depots = {start_depot + 1, end_depot + 1}
    unvisited = (all_nodes - depots) - visited
    if unvisited:
        ux = [coords[i][0] for i in unvisited]
        uy = [coords[i][1] for i in unvisited]
        ax.scatter(
            ux,
            uy,
            marker="x",
            s=NODE_SIZE + 10,
            linewidths=1.2,
            color="black",
            zorder=3,
            label="unvisited",
        )

    depots_same = _depots_coincide(inst, start_depot, end_depot)
    start_key = start_depot + 1
    ax.scatter(
        [coords[start_key][0]],
        [coords[start_key][1]],
        s=160,
        marker="s",
        facecolors="limegreen",
        edgecolors="black",
        linewidths=1.2,
        zorder=4,
        label=(
            f"start/end depot (v={start_depot})"
            if depots_same
            else f"start depot (v={start_depot})"
        ),
    )
    if not depots_same:
        end_key = end_depot + 1
        ax.scatter(
            [coords[end_key][0]],
            [coords[end_key][1]],
            s=160,
            marker="D",
            facecolors="tomato",
            edgecolors="black",
            linewidths=1.2,
            zorder=4,
            label=f"end depot (v={end_depot})",
        )

    ax.set_aspect("equal", adjustable="datalim")
    ax.set_xticks([])
    ax.set_yticks([])
    ax.grid(False)
    ax.set_title(title or "TOP routes")
    ax.legend(loc="center left", bbox_to_anchor=(1.02, 0.5), fontsize=9)


def draw_top(
    inst: TopInstance,
    *,
    agents: list[dict] | None = None,
    title: str | None = None,
    output: Path | None = None,
    show: bool = True,
    dpi: float = 150,
) -> None:
    fig, ax = plt.subplots(figsize=(9, 8))
    if agents:
        draw_top_with_routes(ax, inst, agents, title=title)
    else:
        draw_top_points_only(ax, inst, title=title)

    fig.tight_layout()
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output, dpi=dpi, bbox_inches="tight")
    if show:
        plt.show()
    else:
        plt.close(fig)


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Рисует TOP .txt и опционально маршруты из JSON (интерфейс как utils/draw.py).",
        epilog="Пример как у draw.py:  python draw_top.py map.txt agents.json",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("top_txt", type=Path, help="TOP-инстанс (.txt): n/m/tmax и строки x y S")
    ap.add_argument(
        "agents_json",
        type=Path,
        nargs="?",
        default=None,
        help="Решение с ключом agents (те же индексы 0…n−1, что и у draw.py для vertexes)",
    )
    ap.add_argument("-o", "--output", type=Path, default=None, help="Сохранить PNG/PDF")
    ap.add_argument("--no-show", action="store_true", help="Не открывать окно matplotlib")
    ap.add_argument("--dpi", type=float, default=150)
    ap.add_argument("--title", type=str, default=None, help="Заголовок рисунка")
    ap.add_argument(
        "--depot-loop",
        action="store_true",
        help="Один депо: последняя строка координат в файле отбрасывается (как лишний «финиш» бенчмарка)",
    )
    args = ap.parse_args()

    path = args.top_txt.resolve()
    if not path.is_file():
        print(f"Файл не найден: {path}", file=sys.stderr)
        return 1

    inst = parse_top_path(path, depot_loop=args.depot_loop)
    agents_path = args.agents_json.resolve() if args.agents_json is not None else None
    if agents_path is not None and not agents_path.is_file():
        print(f"Файл не найден: {agents_path}", file=sys.stderr)
        return 1
    agents = _load_agents(agents_path) if agents_path is not None else None

    ttl = args.title
    if ttl is None:
        ttl = f"{path.name}  |  n={inst.n}, m={inst.paths}, tmax={inst.tmax}"

    draw_top(
        inst,
        agents=agents,
        title=ttl,
        output=args.output,
        show=not args.no_show,
        dpi=args.dpi,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
