#include "../include/inner_operation.hpp"

#include <algorithm>
#include <iomanip>
#include <iostream>
#include <vector>
#include <utility>

std::ostream& operator<<(std::ostream& os, const TPath& path) {
    os << "score=" << path.score
       << "\ttime=" << path.time
       << "\tdist=" << path.distance
       << "\tstops=" << path.tour.size() << "\n";
    os << "\troute: 0";
    for (auto v : path.tour) {
        os << "," << v;
    }
    os << ",0\n";
    return os;
}

bool TInnerOperations::DoOperation(TPath& path, const TInputData& inputData,
                                   TInnerOperationContext& context, EInnerOperation operation) {
    static constexpr TInnerOperationFn kOperations[] = {
        &TInnerOperations::SwapAdjacent,  // 0
        &TInnerOperations::SwapAny,       // 1
        &TInnerOperations::Shift,         // 2
        &TInnerOperations::TwoOpt,        // 3
        &TInnerOperations::OrOpt,         // 4
        &TInnerOperations::PickUnvisited  // 5
    };

    constexpr std::size_t kOperationsCount = sizeof(kOperations) / sizeof(kOperations[0]);
    const auto index = static_cast<std::size_t>(static_cast<uint8_t>(operation));
    if (index >= kOperationsCount) {
        return false;
    }

    return (this->*kOperations[index])(path, inputData, context);
}

// меняем местами соседние вершины
bool TInnerOperations::SwapAdjacent(TPath& path, const TInputData& inputData, TInnerOperationContext&) {

    auto initial_score = path.score;

    struct best_operation {
        size_t i;
        int64_t distance;
        int64_t time;
        int64_t score;
    };

    bool found = false;
    best_operation best_swap_adjacent{};

    for (size_t i = 0; i + 1 < path.tour.size(); ++i) {
        path.tour[i] = std::exchange(path.tour[i + 1], path.tour[i]);
        auto [distance, time, score] = inputData.get_path_distance_time_score(path);

        if (initial_score < score && distance <= path.max_distance && time <= path.max_time) {
            found = true;
            best_swap_adjacent = {
                .i = i,
                .distance = distance,
                .time = time,
                .score = score,
            };
            initial_score = score;
        }

        // возврат пути в прежнее состояние
        path.tour[i] = std::exchange(path.tour[i + 1], path.tour[i]);
    }

    if (found) {
        path.tour[best_swap_adjacent.i] = std::exchange(path.tour[best_swap_adjacent.i + 1], path.tour[best_swap_adjacent.i]);
        path.distance = best_swap_adjacent.distance;
        path.time = best_swap_adjacent.time;
        path.score = best_swap_adjacent.score;
    }

    return found;
}

// меняем местами любые две вершины
bool TInnerOperations::SwapAny(TPath& path, const TInputData& inputData, TInnerOperationContext&) {

    auto initial_score = path.score;

    struct best_operation {
        size_t i;
        size_t j;
        int64_t distance;
        int64_t time;
        int64_t score;
    };

    bool found = false;
    best_operation best_swap_any{};

    for (size_t i = 0; i < path.tour.size(); ++i) {
        for (size_t j = i + 1; j < path.tour.size(); ++j) {
            path.tour[i] = std::exchange(path.tour[j], path.tour[i]);
            auto [distance, time, score] = inputData.get_path_distance_time_score(path);

            if (initial_score < score && distance <= path.max_distance && time <= path.max_time) {
                found = true;
                best_swap_any = {
                    .i = i,
                    .j = j,
                    .distance = distance,
                    .time = time,
                    .score = score,
                };
                initial_score = score;
            }

            // возврат пути в прежнее состояние
            path.tour[i] = std::exchange(path.tour[j], path.tour[i]);
        }
    }

    if (found) {
        path.tour[best_swap_any.i] = std::exchange(path.tour[best_swap_any.j], path.tour[best_swap_any.i]);
        path.distance = best_swap_any.distance;
        path.time = best_swap_any.time;
        path.score = best_swap_any.score;
    }

    return found;
}

// перемещает одну вершину на лучшую позицию. O(n^2)
bool TInnerOperations::Shift(TPath& path, const TInputData& inputData, TInnerOperationContext&) {

    auto initial_score = path.score;

    struct best_operation {
        size_t from;
        size_t to;
        int64_t distance;
        int64_t time;
        int64_t score;
    };

    bool found = false;
    best_operation best{};

    for (size_t from = 0; from < path.tour.size(); ++from) {

        auto erased = path.tour;
        const auto vertex = erased[from];
        erased.erase(erased.begin() + from);

        for (size_t to = 0; to < path.tour.size(); ++to) {
            if (from == to) continue;

            erased.insert(erased.begin() + to, vertex);
            std::swap(path.tour, erased);
            auto [distance, time, score] = inputData.get_path_distance_time_score(path);
            std::swap(path.tour, erased);
            erased.erase(erased.begin() + to);

            if (score > initial_score && time <= path.max_time && distance <= path.max_distance) {
                found = true;
                best = {.from = from, .to = to, .distance = distance, .time = time, .score = score};
                initial_score = score;
            }
        }
    }

    if (found) {
        const auto vertex = path.tour[best.from];
        path.tour.erase(path.tour.begin() + best.from);
        path.tour.insert(path.tour.begin() + best.to, vertex);
        path.distance = best.distance;
        path.time     = best.time;
        path.score    = best.score;
    }

    return found;
}

bool TInnerOperations::TwoOpt(TPath& path, const TInputData& inputData, TInnerOperationContext&) {
    auto initial_score = path.score;

    struct best_operation {
        size_t i;
        size_t j;
        int64_t distance;
        int64_t time;
        int64_t score;
    };

    bool found = false;
    best_operation best_two_opt{};

    for (size_t i = 0; i + 1 < path.tour.size(); ++i) {
        for (size_t j = i + 1; j + 1 < path.tour.size(); ++j) {
            std::reverse(path.tour.begin() + i, path.tour.begin() + j + 1);
            auto [distance, time, score] = inputData.get_path_distance_time_score(path);

            if (initial_score < score && distance <= path.max_distance && time <= path.max_time) {
                found = true;
                best_two_opt = {
                    .i = i,
                    .j = j,
                    .distance = distance,
                    .time = time,
                    .score = score,
                };
                initial_score = score;
            }

            // возврат пути в прежнее состояние
            std::reverse(path.tour.begin() + i, path.tour.begin() + j + 1);
        }
    }

    if (found) {
        std::reverse(path.tour.begin() + best_two_opt.i, path.tour.begin() + best_two_opt.j + 1);
        path.distance = best_two_opt.distance;
        path.time = best_two_opt.time;
        path.score = best_two_opt.score;
    }

    return found;
}

// перемещает сегмент из context.orOptSize вершин на лучшую позицию. O(n^2)
bool TInnerOperations::OrOpt(TPath& path, const TInputData& inputData, TInnerOperationContext& context) {
    const size_t n        = path.tour.size();
    const size_t opt_size = std::min(static_cast<size_t>(context.orOptSize), n);

    if (opt_size == 0 || n < opt_size + 1) {
        return false;
    }

    auto initial_score = path.score;

    struct best_operation {
        size_t from;
        size_t to;
        int64_t distance;
        int64_t time;
        int64_t score;
    };

    bool found = false;
    best_operation best{};

    for (size_t from = 0; from + opt_size <= n; ++from) {
        TRoute erased = path.tour;
        std::vector<TRoute::value_type> segment(erased.begin() + from,
                                                erased.begin() + from + opt_size);
        erased.erase(erased.begin() + from, erased.begin() + from + opt_size);

        for (size_t to = 0; to + opt_size <= n; ++to) {
            if (to == from) continue;

            erased.insert(erased.begin() + to, segment.begin(), segment.end());
            std::swap(path.tour, erased);
            auto [distance, time, score] = inputData.get_path_distance_time_score(path);
            std::swap(path.tour, erased);
            erased.erase(erased.begin() + to, erased.begin() + to + opt_size);

            if (score > initial_score && time <= path.max_time && distance <= path.max_distance) {
                found = true;
                best = {.from = from, .to = to, .distance = distance, .time = time, .score = score};
                initial_score = score;
            }
        }
    }

    if (found) {
        std::vector<TRoute::value_type> segment(path.tour.begin() + best.from, path.tour.begin() + best.from + opt_size);
        path.tour.erase(path.tour.begin() + best.from, path.tour.begin() + best.from + opt_size);
        path.tour.insert(path.tour.begin() + best.to, segment.begin(), segment.end());
        path.distance = best.distance;
        path.time     = best.time;
        path.score    = best.score;
    }

    return found;
}

// пытается добавить в путь ещё непосещённую никем вершину
bool TInnerOperations::PickUnvisited(TPath& path, const TInputData& inputData, TInnerOperationContext& context) {

    if (path.tour.size() == path.max_vertexes) {
        return false;
    }

    auto initial_score = path.score;

    auto candidates = ChooseUnvisitedVertexes(inputData, std::max(context.unvisiedCandidatesCount, 1ul));

    struct best_operation {
        TRoute::value_type vertex;
        size_t to;
        int64_t distance;
        int64_t time;
        int64_t score;
    };

    bool found = false;
    best_operation best{};

    for (auto candidate : candidates) {
        for (size_t to = 0; to < path.tour.size(); ++to) {
            path.tour.insert(path.tour.begin() + to, candidate);
            auto [distance, time, score] = inputData.get_path_distance_time_score(path);
            if (score > initial_score && time <= path.max_time && distance <= path.max_distance) {
                found = true;
                best = {.vertex = candidate, .to = to, .distance = distance, .time = time, .score = score};
                initial_score = score;
            }
            path.tour.erase(path.tour.begin() + to);
        }
    }

    if (found) {

        std::cout << "Added new vertex for tour: " << path << "\n and vertex: " << best.vertex << "\n";

        path.tour.insert(path.tour.begin() + best.to, best.vertex);
        path.distance = best.distance;
        path.time     = best.time;
        path.score    = best.score;

        inputData.visited_points.insert(best.vertex);
        auto it = std::find_if(inputData.unvisited_points.begin(), inputData.unvisited_points.end(),
            [&](const auto m) { return m == best.vertex; });
        if (it == inputData.unvisited_points.end()) { [[unlikely]]
            std::cout << "Error -- want delete already visited point: " <<best.vertex << " for agent #" << path.agent_idx << "\n"; 
        } else {
            inputData.unvisited_points.erase(it);
        }
    }

    return found;
}
