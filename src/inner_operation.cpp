#include "../include/inner_operation.hpp"
#include "../utils/problem_arguments_impl.hpp"

#include <algorithm>
#include <iomanip>
#include <iostream>
#include <vector>
#include <utility>
#include <random>

#include <cassert>

namespace {
    using points_type = TRoute::value_type;

    std::vector<points_type> ChooseUnvisitedVertexes(const TInputData& input, size_t vertexes) {
        thread_local std::mt19937 rng{std::random_device{}()};
        vertexes = std::min(vertexes, input.unvisited_points.size());

        std::shuffle(input.unvisited_points.begin(), input.unvisited_points.end(), rng);
        std::vector<points_type> chosen(input.unvisited_points.begin(), input.unvisited_points.begin() + vertexes);
        return chosen;
    }

} // namespace

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
        &TInnerOperations::PickUnvisited, // 5
        &TInnerOperations::Drop           // 6
    };

    constexpr std::size_t kOperationsCount = sizeof(kOperations) / sizeof(kOperations[0]);
    const auto index = static_cast<std::size_t>(static_cast<uint8_t>(operation));
    assert(index < kOperationsCount);
    if (index >= kOperationsCount) {
        return false;
    }

    return (this->*kOperations[index])(path, inputData, context);
}

// меняем местами соседние вершины
bool TInnerOperations::SwapAdjacent(TPath& path, const TInputData& inputData, TInnerOperationContext&) {
    auto initial_score = path.score;

    struct best_operation { size_t i; int64_t distance, time, score; };
    bool found = false;
    best_operation best{};

    for (size_t i = 0; i + 1 < path.tour.size(); ++i) {
        // виртуально меняем местами вершины tour[i] и toru[i+1]
        auto [distance, time, score] = inputData.EvalVirtualTour(path, path.tour.size(),
            [&](size_t pos) -> points_type {
                if (pos == i) return path.tour[i + 1];
                if (pos == i + 1) return path.tour[i];
                return path.tour[pos];
            });

        if (initial_score < score && distance <= path.max_distance && time <= path.max_time) {
            found = true;
            best = {.i = i, .distance = distance, .time = time, .score = score};
            initial_score = score;
        }
    }

    if (found) {
        std::swap(path.tour[best.i], path.tour[best.i + 1]);
        path.distance = best.distance;
        path.time = best.time;
        path.score = best.score;
    }
    return found;
}

// меняет местами две любые вершины
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
    best_operation best{};

    for (size_t i = 0; i < path.tour.size(); ++i) {
        for (size_t j = i + 1; j < path.tour.size(); ++j) {
            // делаем виртуальную замену вершин tour[i] и tour[j] 
            auto [distance, time, score] = inputData.EvalVirtualTour(path, path.tour.size(),
                [&](size_t pos) -> points_type {
                    if (pos == i) return path.tour[j];
                    if (pos == j) return path.tour[i];
                    return path.tour[pos];
                });

            if (initial_score < score && distance <= path.max_distance && time <= path.max_time) {
                found = true;
                best = {.i = i, .j = j, .distance = distance, .time = time, .score = score};
                initial_score = score;
            }
        }
    }

    if (found) {
        std::swap(path.tour[best.i], path.tour[best.j]);
        path.distance = best.distance;
        path.time = best.time;
        path.score = best.score;
    }
    return found;
}

// делает циклический свдиг подотрезка
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

    auto get_shifted = [&](size_t from, size_t to, size_t pos) -> points_type {
        if (pos == to) return path.tour[from];
        // позиция до вставки в to
        size_t original_pos = pos < to ? pos : pos - 1;
        // позиция до удаления from
        original_pos = original_pos < from ? original_pos : original_pos + 1;
        return path.tour[original_pos];
    };

    for (size_t from = 0; from < path.tour.size(); ++from) {
        for (size_t to = 0; to < path.tour.size(); ++to) {
            if (from == to) continue;

            auto [distance, time, score] = inputData.EvalVirtualTour(path, path.tour.size(),
                [&](size_t pos) { return get_shifted(from, to, pos); });

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
        path.time = best.time;
        path.score = best.score;
    }
    return found;
}

// разворачивает сегмент [i..j]
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
    best_operation best{};

    for (size_t i = 0; i + 1 < path.tour.size(); ++i) {
        for (size_t j = i + 1; j + 1 < path.tour.size(); ++j) {
            // виртуально разворачиваем tour[i..j] 
            auto [distance, time, score] = inputData.EvalVirtualTour(path, path.tour.size(),
                [&](size_t pos) -> points_type {
                    if (i <= pos && pos <= j) return path.tour[i + j - pos];
                    return path.tour[pos];
                });

            if (initial_score < score && distance <= path.max_distance && time <= path.max_time) {
                found = true;
                best = {.i = i, .j = j, .distance = distance, .time = time, .score = score};
                initial_score = score;
            }
        }
    }

    if (found) {
        std::reverse(path.tour.begin() + best.i, path.tour.begin() + best.j + 1);
        path.distance = best.distance;
        path.time = best.time;
        path.score = best.score;
    }
    return found;
}

// перемещает сегмент длины seg_len на новую позицию
bool TInnerOperations::OrOpt(TPath& path, const TInputData& inputData, TInnerOperationContext& context) {

    const size_t seg_len = std::min(static_cast<size_t>(context.orOptSize), path.tour.size());

    if (seg_len == 0 || path.tour.size() < seg_len + 1) {
        return false;
    }

    auto initial_score = path.score;

    struct best_operation {
        size_t from;
        size_t to;
        int64_t distance;
        int64_t time;
        int64_t score;
        bool reversed;
    };

    bool found = false;
    best_operation best{};

    for (size_t from = 0; from + seg_len <= path.tour.size(); ++from) {
        for (size_t to = 0; to + seg_len <= path.tour.size(); ++to) {
            if (to == from) continue;
            for (auto reversed : {true, false}) {
                auto [distance, time, score] = inputData.EvalVirtualTour(path, path.tour.size(),
                    [&](size_t pos) -> points_type {
                        // если позиция из вставленного подотрезка 
                        if (to <= pos && pos < to + seg_len) {
                            if (!reversed) {
                                return path.tour[from + (pos - to)];
                            } else {
                                return path.tour[from + (seg_len - 1 - (pos - to))];
                            }
                        }
                        size_t original_pos = pos < to ? pos : pos - seg_len;
                        original_pos = (original_pos < from) ? original_pos : original_pos + seg_len;
                        return path.tour[original_pos];
                    });

                if (score > initial_score && time <= path.max_time && distance <= path.max_distance) {
                    found = true;
                    best = {.from = from, .to = to, .distance = distance, .time = time, .score = score, .reversed = reversed};
                    initial_score = score;
                }
            }
        }
    }

    if (found) {
        std::vector<TRoute::value_type> segment(path.tour.begin() + best.from, path.tour.begin() + best.from + seg_len);
        if (best.reversed) {
            std::reverse(segment.begin(), segment.end());
        }
        path.tour.erase(path.tour.begin() + best.from, path.tour.begin() + best.from + seg_len);
        path.tour.insert(path.tour.begin() + best.to, segment.begin(), segment.end());
        path.distance = best.distance;
        path.time = best.time;
        path.score = best.score;
    }
    return found;
}

// пытается добавить еще непосещенную вершину в путь
bool TInnerOperations::PickUnvisited(TPath& path, const TInputData& inputData, TInnerOperationContext& context) {
    if (path.tour.size() >= path.max_vertexes) {
        return false;
    }

    auto initial_score = path.score;

    auto candidates_list = ChooseUnvisitedVertexes(inputData, std::max(context.unvisiedCandidatesCount, 1ul));

    struct best_operation { TRoute::value_type vertex; size_t to; int64_t distance, time, score; };
    bool found = false;
    best_operation best{};

    for (auto candidate : candidates_list) {
        for (size_t to = 0; to <= path.tour.size(); ++to) {
            auto [distance, time, score] = inputData.EvalVirtualTour(path, path.tour.size() + 1,
                [&](size_t pos) -> points_type {
                    if (pos == to) return candidate;
                    return path.tour[pos < to ? pos : pos - 1];
                });

            if (score > initial_score && time <= path.max_time && distance <= path.max_distance) {
                found = true;
                best = {.vertex = candidate, .to = to, .distance = distance, .time = time, .score = score};
                initial_score = score;
            }
        }
    }

    if (found) {
        path.tour.insert(path.tour.begin() + best.to, best.vertex);
        path.distance = best.distance;
        path.time = best.time;
        path.score = best.score;

        inputData.visited_points.insert(best.vertex);
        const auto& it = std::find(inputData.unvisited_points.begin(), inputData.unvisited_points.end(), best.vertex);
        if (it != inputData.unvisited_points.end()) [[likely]] {
            inputData.unvisited_points.erase(it);
        } else {
            std::cout << "Error: want delete already visited point: " << best.vertex << " for agent #" << path.agent_idx << "\n";
        }
    }
    return found;
}

// пытаемся удалить вершину из пути
bool TInnerOperations::Drop(TPath& path, const TInputData& inputData, TInnerOperationContext& context) {
    if (path.tour.size() <= path.min_vertexes) {
        return false;
    }

    auto initial_score = path.score;

    struct best_operation {size_t idx; int64_t distance, time, score; };
    bool found = false;
    best_operation best{};

    for (size_t i = 0; i < path.tour.size(); ++i) {

        auto [distance, time, score] = inputData.EvalVirtualTour(path, path.tour.size() - 1,
            [&](size_t pos) -> points_type {
                if (pos < i) {
                    return path.tour[pos];
                } else {
                    return path.tour[pos + 1];
                }
            });

        if (score > initial_score && time <= path.max_time && distance <= path.max_distance) {
            found = true;
            best = {.idx = i, .distance = distance, .time = time, .score = score};
        }
                
    }

    if (found) {
        auto elem = path.tour[best.idx];
        path.tour.erase(path.tour.begin() + best.idx);
        path.distance = best.distance;
        path.time = best.time;
        path.score = best.score;

        inputData.unvisited_points.emplace_back(elem);
        inputData.visited_points.erase(elem);
    }
    return found;
}