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
        &TInnerOperations::Drop,          // 6
        &TInnerOperations::Replace,       // 7
        &TInnerOperations::DoubleBridge,  // 8
    };

    const auto index = static_cast<std::size_t>(static_cast<uint8_t>(operation));
    assert(index < kInnerOperationsCount);
    if (index >= kInnerOperationsCount) {
        return false;
    }

    auto answer = (this->*kOperations[index])(path, inputData, context);

    inputData.check_path_values(path);
    return answer;
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
    // отдаем приоритет набору минимального числа вершин в маршруте чем целевой функции
    if (path.tour.size() < path.min_vertexes) {
        initial_score = std::numeric_limits<decltype(initial_score)>::min() + 1;
    }

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
            initial_score = score;
            best = {.idx = i, .distance = distance, .time = time, .score = score};
        }
                
    }

    if (found) {
        auto elem = path.tour[best.idx];
        path.tour.erase(path.tour.begin() + best.idx);
        path.distance = best.distance;
        path.time = best.time;
        path.score = best.score;

        if (std::find(inputData.unvisited_points.begin(), inputData.unvisited_points.end(), elem) == inputData.unvisited_points.end()) {
            inputData.unvisited_points.emplace_back(elem);
        } else {
            std::cout << "Error: want to add already unvisited point: " << elem << " for agent #" << path.agent_idx << "\n";
        }
        inputData.visited_points.erase(elem);
    }
    return found;
}

// заменить вершину из пути на непосещенную
bool TInnerOperations::Replace(TPath& path, const TInputData& inputData, TInnerOperationContext& context) {
    if (path.tour.empty() || inputData.unvisited_points.empty()) {
        return false;
    }

    auto initial_score = path.score;

    struct best_operation {
        size_t remove_idx;
        points_type insert_vertex;
        size_t insert_pos;
        int64_t distance, time, score;
    };

    bool found = false;
    best_operation best{};

    auto candidates = ChooseUnvisitedVertexes(inputData, std::max(context.unvisiedCandidatesCount, 1ul));

    for (size_t remove_idx = 0; remove_idx < path.tour.size(); ++remove_idx) {
        for (auto candidate : candidates) {
            for (size_t insert_pos = 0; insert_pos < path.tour.size(); ++insert_pos) {

                auto [distance, time, score] = inputData.EvalVirtualTour(path, path.tour.size(),
                    [&](size_t pos) -> points_type {
                        if (pos == insert_pos) {
                            return candidate;
                        }

                        // индекс в туре после удаления
                        size_t j = pos < insert_pos ? pos : pos - 1;

                        // маппинг к исходному
                        if (j < remove_idx) {
                            return path.tour[j];
                        } else {
                            return path.tour[j + 1];
                        }
                    });

                if (score > initial_score && time <= path.max_time && distance <= path.max_distance) {
                    found = true;
                    best = {
                        .remove_idx = remove_idx, 
                        .insert_vertex = candidate, 
                        .insert_pos = insert_pos, 
                        .distance = distance, 
                        .time = time, 
                        .score = score
                    };
                    initial_score = score;
                }
            }
        }
    }

    if (found) {
        const auto removed_vertex = path.tour[best.remove_idx];

        path.tour.erase(path.tour.begin() + best.remove_idx);
        path.tour.insert(path.tour.begin() + best.insert_pos, best.insert_vertex);

        path.distance = best.distance;
        path.time = best.time;
        path.score = best.score;

        inputData.visited_points.erase(removed_vertex);
        inputData.visited_points.insert(best.insert_vertex);

        auto it_added= std::find(inputData.unvisited_points.begin(),
                                 inputData.unvisited_points.end(), best.insert_vertex);
        if (it_added != inputData.unvisited_points.end()) {
            inputData.unvisited_points.erase(it_added);
        } else {
            std::cout << "Error Replace: insert_vertex:" <<  best.insert_vertex << " not in unvisited for agent #"  << path.agent_idx << std::endl;
        }

        auto it_removed = std::find(inputData.unvisited_points.begin(),
                                    inputData.unvisited_points.end(), removed_vertex);
        if (it_removed == inputData.unvisited_points.end()) {
            inputData.unvisited_points.push_back(removed_vertex);
        } else {
            std::cout << "Error Replace: removed_vertex: " << removed_vertex << " already in unvisited for agent #" << path.agent_idx << std::endl;
        }
    }
    return found;
}

// Источник: Vansteenwegen et al. (2009) «ILS for TOPTW» (Computers & OR)
bool TInnerOperations::DoubleBridge(TPath& path, const TInputData& inputData, TInnerOperationContext&) {

    if (path.tour.size() < 8) {
        return false;
    }

    thread_local std::mt19937 rng{std::random_device{}()};

    std::uniform_int_distribution<size_t> dist(1, path.tour.size() - 1);
    size_t cut1 = dist(rng);
    size_t cut2 = dist(rng);
    size_t cut3 = dist(rng);

    // Убеждаемся что разрезы различны и упорядочены
    while (cut1 == cut2 || cut1 == cut3 || cut2 == cut3) {
        cut1 = dist(rng);
        cut2 = dist(rng);
        cut3 = dist(rng);
    }

    if (cut1 > cut2) {
        std::swap(cut1, cut2);
    }
    if (cut2 > cut3) {
        std::swap(cut2, cut3);
    }
    if (cut1 > cut2){ 
        std::swap(cut1, cut2);
    }

    // сегменты A=[0,cut1), B=[cut1,cut2), C=[cut2,cut3), D=[cut3,n)
    // Новый порядок: A-B-C-D -> A-C-B-D
    TRoute new_tour;
    new_tour.reserve(path.tour.size());
    new_tour.insert(new_tour.end(), path.tour.begin(), path.tour.begin() + cut1);
    new_tour.insert(new_tour.end(), path.tour.begin() + cut2, path.tour.begin() + cut3);
    new_tour.insert(new_tour.end(), path.tour.begin() + cut1, path.tour.begin() + cut2);
    new_tour.insert(new_tour.end(), path.tour.begin() + cut3, path.tour.end());

    std::swap(path.tour, new_tour);
    auto [distance, time, score] = inputData.get_path_distance_time_score(path);
    if (distance <= path.max_distance && time <= path.max_time && score > path.score) {
        path.distance = distance;
        path.time = time;
        path.score = score;
        return true;
    } else {
        std::swap(path.tour, new_tour);
    }

    return false;
}