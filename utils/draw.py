import json
import matplotlib.pyplot as plt


def parse_cvrp(file_path):
    coords = {}
    dimension = None
    section = None

    with open(file_path, "r") as f:
        for line in f:
            line = line.strip()

            if line.startswith("DIMENSION"):
                dimension = int(line.split(":")[1])

            elif line.startswith("NODE_COORD_SECTION"):
                section = "coords"
                continue
            elif line.startswith("DEMAND_SECTION"):
                break

            if section == "coords":
                parts = line.split()
                if len(parts) == 3:
                    i, x, y = parts
                    coords[int(i)] = (float(x), float(y))

    return coords, dimension


def draw_routes(coords, dimension, agents):
    plt.figure(figsize=(8, 8))

    visited = set()

    # 🔹 рисуем маршруты
    for agent in agents:
        route = agent["vertexes"]

        xs, ys = [], []

        for v in route:
            node_id = v + 1  # 0-based → 1-based
            visited.add(node_id)

            x, y = coords[node_id]
            xs.append(x)
            ys.append(y)

        plt.plot(xs, ys, marker='o', label=f'agent {agent["index"]}')

    # 🔹 депо
    depot_x, depot_y = coords[1]
    plt.scatter(depot_x, depot_y, s=200, marker='s', label='depot')

    # 🔹 непосещённые вершины
    all_nodes = set(range(1, dimension + 1))
    unvisited = all_nodes - visited

    if unvisited:
        ux = [coords[i][0] for i in unvisited]
        uy = [coords[i][1] for i in unvisited]

        plt.scatter(ux, uy, marker='x', s=100, label='unvisited')

    plt.title("VRP Routes with Unvisited Nodes")
    plt.legend(loc='center left', bbox_to_anchor=(1, 0.5))
    plt.grid(True)
    plt.show()


def main():
    import sys

    if len(sys.argv) < 3:
        print("Usage: python draw.py input.txt agents.json")
        return

    input_file = sys.argv[1]
    agents_file = sys.argv[2]

    coords, dimension = parse_cvrp(input_file)

    with open(agents_file, "r") as f:
        agents_data = json.load(f)

    draw_routes(coords, dimension, agents_data["agents"])


if __name__ == "__main__":
    main()