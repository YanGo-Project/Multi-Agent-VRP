import json
import math
import sys


def parse_cvrp(file_path):
    coords = {}
    demand = {}
    dimension = None
    capacity = None

    section = None

    with open(file_path, "r") as f:
        for line in f:
            line = line.strip()

            if not line:
                continue

            if line.startswith("DIMENSION"):
                dimension = int(line.split(":")[1])
            elif line.startswith("CAPACITY"):
                capacity = int(line.split(":")[1])
            elif line.startswith("NODE_COORD_SECTION"):
                section = "coords"
                continue
            elif line.startswith("DEMAND_SECTION"):
                section = "demand"
                continue
            elif line.startswith("DEPOT_SECTION"):
                section = "depot"
                continue
            elif line.startswith("EOF"):
                break

            if section == "coords":
                parts = line.split()
                if len(parts) == 3:
                    i, x, y = parts
                    coords[int(i)] = (float(x), float(y))

            elif section == "demand":
                parts = line.split()
                if len(parts) == 2:
                    i, d = parts
                    demand[int(i)] = int(d)

    return {
        "dimension": dimension,
        "capacity": capacity,
        "coords": coords,
        "demand": demand
    }


def euclidean(a, b):
    return int(round(math.sqrt((a[0]-b[0])**2 + (a[1]-b[1])**2)))


def build_distance_matrix(coords, n):
    return [
        [euclidean(coords[i], coords[j]) for j in range(n)]
        for i in range(n)
    ]


def convert(data, min_load, max_load):
    n = data["dimension"]

    # перенумерация (1..N → 0..N-1)
    coords = {i-1: data["coords"][i] for i in data["coords"]}
    demand = {i-1: data["demand"][i] for i in data["demand"]}

    distance_matrix = build_distance_matrix(coords, n)

    # time_matrix = копия (1 временной слой)
    time_matrix = [distance_matrix]

    # оценки и сервис таймы (без депо)
    point_scores = [demand[i] for i in range(1, n)]
    point_service_times = [0 for _ in range(n-1)]

    # максимальное расстояние (очень большое)
    max_dist = max(max(row) for row in distance_matrix)
    max_distance = max_dist * n

    # аналогично время
    max_time = max_distance

    return {
        "points_count": n,
        "min_load": min_load,
        "max_load": max_load,
        "max_time": max_time,
        "max_distance": max_distance,
        "distance_matrix": distance_matrix,
        "time_matrix": time_matrix,
        "point_scores": point_scores,
        "point_service_times": point_service_times
    }


def main():
    if len(sys.argv) < 5:
        print("Usage: python convert.py input.txt output.json min_load max_load")
        return

    input_file = sys.argv[1]
    output_file = sys.argv[2]
    min_load = int(sys.argv[3])
    max_load = int(sys.argv[4])

    data = parse_cvrp(input_file)
    result = convert(data, min_load, max_load)

    with open(output_file, "w") as f:
        json.dump(result, f, indent=2)

    print(f"Saved to {output_file}")


if __name__ == "__main__":
    main()