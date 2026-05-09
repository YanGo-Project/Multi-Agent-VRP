# """
# Отрисовка маршрутов из agents JSON поверх координат исходного TSPLIB .vrp.

# Соглашение об индексах (как после scripts/cvrplib_vrp_to_json.py):
#   • В JSON задачи и в маршруте solver: вершины 0 … points_count−1, депо = 0.
#   • В файле .vrp узлы 1 … DIMENSION (TSPLIB), депо в ваших данных — узел 1.
#   • Перенумерация депо в матрице (remap_depot_to_index_zero) для депо≠1 здесь
#     не компенсируется — для корректной картинки нужен тот же .vrp, что при конвертации.

# Отображение: node_id = v + 1 подтягивает координаты NODE_COORD_SECTION для узла с номером v+1.
# Без равного масштаба осей (aspect equal) карта визуально «плывёт» относительно оригинала.
# """
# import colorsys
# import json
# import re

# import matplotlib.pyplot as plt

# # Золотое сечение: равномерно «обходим» круг оттенков без скоплений в одном секторе.
# _PHI = 0.618033988749895


# def _colors_for_n_agents(n: int):
#     """
#     Различимые цвета: turbo и линейное распределение дают сливающиеся соседние оттенки.
#     Для n≤20 — готовая палитра tab20; иначе HSV с шагом hue по φ и разными S/V.
#     """
#     if n <= 0:
#         return []
#     if n <= 20:
#         cmap = plt.colormaps["tab20"]
#         return [cmap((i + 0.5) / 20) for i in range(n)]

#     out: list[tuple[float, float, float]] = []
#     for i in range(n):
#         h = (i * _PHI + 0.04) % 1.0
#         # Несколько ступеней S и V, чтобы соседние по списку агенты не были «рядом» в цвете
#         s = 0.62 + 0.34 * ((i * 2) % 5) / 4.0
#         v = 0.72 + 0.24 * ((i * 3) % 4) / 3.0
#         out.append(colorsys.hsv_to_rgb(h, s, v))
#     return out


# def parse_cvrp(file_path):
#     coords = {}
#     dimension = None
#     depot_node = 1
#     section = None

#     with open(file_path, "r") as f:
#         raw = f.read()

#     # DEPOT_SECTION может идти после DEMAND — читаем целиком
#     m_dep = re.search(
#         r"(?im)^DEPOT_SECTION\s*\n\s*(\d+)",
#         raw,
#     )
#     if m_dep:
#         depot_node = int(m_dep.group(1))

#     for line in raw.splitlines():
#         line = line.strip()

#         if line.startswith("DIMENSION"):
#             dimension = int(line.split(":")[1])

#         elif line.startswith("NODE_COORD_SECTION"):
#             section = "coords"
#             continue
#         elif line.startswith("DEMAND_SECTION"):
#             section = None
#             continue

#         if section == "coords":
#             parts = line.split()
#             if len(parts) == 3:
#                 i, x, y = parts
#                 coords[int(i)] = (float(x), float(y))

#     return coords, dimension, depot_node


# def draw_routes(coords, dimension, agents, depot_node: int = 1):
#     fig, ax = plt.subplots(figsize=(8, 8))

#     visited = set()
#     colors = _colors_for_n_agents(len(agents))
#     # Дополнительно разные маркеры на случай печати в Ч/Б
#     markers = ("o", "s", "^", "v", "D", "P", "X", "*", "h", "p")

#     # 🔹 рисуем маршруты
#     for i, agent in enumerate(agents):
#         route = agent["vertexes"]

#         xs, ys = [], []

#         for v in route:
#             node_id = v + 1  # индекс JSON (как в матрице) → номер узла TSPLIB
#             visited.add(node_id)

#             x, y = coords[node_id]
#             xs.append(x)
#             ys.append(y)

#         idx = agent.get("index", i)
#         ax.plot(
#             xs,
#             ys,
#             marker=markers[i % len(markers)],
#             color=colors[i],
#             linewidth=2.0,
#             markersize=5,
#             markeredgecolor="white",
#             markeredgewidth=0.7,
#             label=f"agent {idx}",
#         )

#     # 🔹 депо (номер узла из DEPOT_SECTION, по умолчанию 1 — как у Augerat P)
#     depot_x, depot_y = coords[depot_node]
#     ax.scatter(depot_x, depot_y, s=200, marker="s", label="depot", zorder=5)

#     # 🔹 непосещённые вершины
#     all_nodes = set(range(1, dimension + 1))
#     unvisited = all_nodes - visited

#     if unvisited:
#         ux = [coords[i][0] for i in unvisited]
#         uy = [coords[i][1] for i in unvisited]

#         ax.scatter(ux, uy, marker="x", s=100, label="unvisited")

#     ax.set_title("VRP Routes with Unvisited Nodes")
#     # Иначе matplotlib растягивает оси — карта не совпадает по пропорциям с оригиналом
#     ax.set_aspect("equal", adjustable="datalim")
#     ax.legend(loc="center left", bbox_to_anchor=(1, 0.5))
#     fig.tight_layout()
#     plt.show()


# def main():
#     import sys

#     if len(sys.argv) < 3:
#         print("Usage: python draw.py input.txt agents.json")
#         return

#     input_file = sys.argv[1]
#     agents_file = sys.argv[2]

#     coords, dimension, depot_node = parse_cvrp(input_file)

#     with open(agents_file, "r") as f:
#         agents_data = json.load(f)

#     draw_routes(coords, dimension, agents_data["agents"], depot_node=depot_node)


# if __name__ == "__main__":
#     main()

import colorsys
import json
import re

import matplotlib.pyplot as plt

_PHI = 0.618033988749895


def _colors_for_n_agents(n: int):
    if n <= 0:
        return []
    if n <= 20:
        cmap = plt.colormaps["tab20"]
        return [cmap((i + 0.5) / 20) for i in range(n)]

    out = []
    for i in range(n):
        h = (i * _PHI + 0.04) % 1.0
        s = 0.65
        v = 0.85
        out.append(colorsys.hsv_to_rgb(h, s, v))
    return out


def parse_cvrp(file_path):
    coords = {}
    dimension = None
    depot_node = 1
    section = None

    with open(file_path, "r") as f:
        raw = f.read()

    m_dep = re.search(r"(?im)^DEPOT_SECTION\s*\n\s*(\d+)", raw)
    if m_dep:
        depot_node = int(m_dep.group(1))

    for line in raw.splitlines():
        line = line.strip()

        if line.startswith("DIMENSION"):
            dimension = int(line.split(":")[1])

        elif line.startswith("NODE_COORD_SECTION"):
            section = "coords"
            continue
        elif line.startswith("DEMAND_SECTION"):
            section = None
            continue

        if section == "coords":
            parts = line.split()
            if len(parts) == 3:
                i, x, y = parts
                coords[int(i)] = (float(x), float(y))

    return coords, dimension, depot_node


def draw_routes(coords, dimension, agents, depot_node=1):
    fig, ax = plt.subplots(figsize=(8, 8))

    NODE_SIZE = 40
    visited = set()
    colors = _colors_for_n_agents(len(agents))

    # 🔹 маршруты + вершины (в цвет маршрута)
    for i, agent in enumerate(agents):
        route = agent["vertexes"]

        xs, ys = [], []
        vx, vy = [], []

        for v in route:
            node_id = v + 1
            visited.add(node_id)

            x, y = coords[node_id]
            xs.append(x)
            ys.append(y)
            vx.append(x)
            vy.append(y)

        # линия маршрута
        ax.plot(
            xs,
            ys,
            color=colors[i],
            linewidth=2.5,
            solid_capstyle="round",
            alpha=0.9,
            zorder=2,
        )

        # вершины маршрута
        ax.scatter(
            vx,
            vy,
            s=NODE_SIZE,
            color=colors[i],
            edgecolors="black",
            linewidths=0.5,
            zorder=3,
        )

    # 🔹 непосещённые вершины
    all_nodes = set(range(1, dimension + 1))
    unvisited = all_nodes - visited

    if unvisited:
        ux = [coords[i][0] for i in unvisited]
        uy = [coords[i][1] for i in unvisited]

        ax.scatter(
            ux,
            uy,
            marker="x",
            s=NODE_SIZE,
            linewidths=1.2,
            color="black",
            zorder=3,
            label="unvisited",
        )

    # 🔹 депо
    depot_x, depot_y = coords[depot_node]

    ax.scatter(
        depot_x,
        depot_y,
        s=120,
        marker="s",
        facecolors="red",
        edgecolors="black",
        linewidths=1.2,
        zorder=4,
        label="depot",
    )

    # 🔹 оформление
    ax.set_title("VRP Routes")
    ax.set_aspect("equal", adjustable="datalim")

    ax.set_xticks([])
    ax.set_yticks([])
    ax.grid(False)

    fig.tight_layout()
    plt.show()


def main():
    import sys

    if len(sys.argv) < 3:
        print("Usage: python draw.py input.vrp agents.json")
        return

    input_file = sys.argv[1]
    agents_file = sys.argv[2]

    coords, dimension, depot_node = parse_cvrp(input_file)

    with open(agents_file, "r") as f:
        agents_data = json.load(f)

    draw_routes(coords, dimension, agents_data["agents"], depot_node)


if __name__ == "__main__":
    main()