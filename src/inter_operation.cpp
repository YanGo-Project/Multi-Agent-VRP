#include "../include/inter_operation.hpp"
#include "../include/algorithm.hpp"
#include "../include/operator_selector.hpp"
#include "../utils/problem_arguments_impl.hpp"

#include <algorithm>
#include <cassert>
#include <limits>
#include <cstring>
#include <iomanip>
#include <iostream>

namespace {
    using points_type = TRoute::value_type;
} // namespace

bool TInterOperations::DoOperation(TPath& path1, TPath& path2, const TInputData& inputData,
                                   EInterOperation operation, TInterOperationContext& ctx) {
    static constexpr TOperationFn kOperations[] = {
        &TInterOperations::Relocate,        // 0
        &TInterOperations::Swap,            // 1
        &TInterOperations::TwoOpt,          // 2
        &TInterOperations::Cross,           // 3
        &TInterOperations::RelocateSegment, // 4
        &TInterOperations::Glue,            // 5
    };

    const uint8_t idx = static_cast<uint8_t>(operation);
    assert(idx < kInterOperationsCount);
    if (idx >= kInterOperationsCount) {
        return false;
    }

    auto answer = (this->*kOperations[idx])(path1, path2, inputData, ctx);

    inputData.check_path_values(path1);
    inputData.check_path_values(path2);
    return answer;
}

// переместить одну вершину пути в другой путь
bool TInterOperations::Relocate(TPath& path1, TPath& path2, const TInputData &inputData, TInterOperationContext&) {
    auto initial_score = path1.score + path2.score;

    // в случае если один из путей не имеет минимального числа вершин, то отдаем его добору приоритет над целевой функцией
    if (path1.tour.size() < path1.min_vertexes || path2.tour.size() < path2.min_vertexes) {
        initial_score = std::numeric_limits<decltype(initial_score)>::min();
    }

    struct best_operation {
        bool from_first;
        size_t from_idx;
        size_t to_idx;
        int64_t src_distance;
        int64_t src_time;
        int64_t src_score;
        int64_t dst_distance;
        int64_t dst_time;
        int64_t dst_score;
    };

    bool found = false;
    best_operation best_relocation{};

    // src -> dst: пробуем переместить вершину из src в dst и ищем лучший вариант
    auto try_relocate_direction = [&](TPath& src, TPath& dst, bool from_first) {
        if (src.tour.size() <= src.min_vertexes || dst.tour.size() >= dst.max_vertexes) {
            return;
        }

        for (size_t from = 0; from < src.tour.size(); ++from) {

            auto [distance1, time1, score1] = inputData.EvalVirtualTour(src, src.tour.size() - 1,
                    [&](size_t pos) -> points_type {
                        if (pos < from) return src.tour[pos];
                        return src.tour[pos + 1];
                    });

            for (size_t to = 0; to <= dst.tour.size(); ++to) {
                auto [distance2, time2, score2] = inputData.EvalVirtualTour(dst, dst.tour.size() + 1,
                        [&](size_t pos) -> points_type {
                            if (pos == to) return src.tour[from];
                            if (pos < to) { 
                                return dst.tour[pos];
                            } else {
                                return dst.tour[pos - 1];
                            }
                        });
                
                if (distance1 <= src.max_distance && distance2 <= dst.max_distance &&
                    time1 <= src.max_time && time2 <= dst.max_time &&
                    score1 + score2 > initial_score) {

                    found = true;
                    best_relocation = {
                        .from_first   = from_first,
                        .from_idx     = from,
                        .to_idx       = to,
                        .src_distance = distance1,
                        .src_time     = time1,
                        .src_score    = score1,
                        .dst_distance = distance2,
                        .dst_time     = time2,
                        .dst_score    = score2,
                    };
                    initial_score = score1 + score2;
                }
            }
        }
    };

    try_relocate_direction(path1, path2, true);
    try_relocate_direction(path2, path1, false);

    if (found) {
        TPath& src = best_relocation.from_first ? path1 : path2;
        TPath& dst = best_relocation.from_first ? path2 : path1;

        const auto element = src.tour[best_relocation.from_idx];
        src.tour.erase(src.tour.begin() + best_relocation.from_idx);
        dst.tour.insert(dst.tour.begin() + best_relocation.to_idx, element);

        src.distance = best_relocation.src_distance;
        src.time = best_relocation.src_time;
        src.score = best_relocation.src_score;
        dst.distance = best_relocation.dst_distance;
        dst.time = best_relocation.dst_time;
        dst.score = best_relocation.dst_score;
    }

    return found;
}

// обмен двух вершин между путями
bool TInterOperations::Swap(TPath& path1, TPath& path2, const TInputData &inputData, TInterOperationContext&) {
    auto initial_score = path1.score + path2.score;

    struct best_operation {
        size_t path1_idx;
        int64_t distance1;
        int64_t time1;
        int64_t score1;
        size_t path2_idx;
        int64_t distance2;
        int64_t time2;
        int64_t score2;
    };

    bool found = false;
    best_operation best_swap{};

    for (size_t path1_idx = 0; path1_idx < path1.tour.size(); ++path1_idx) {
        for (size_t path2_idx = 0; path2_idx < path2.tour.size(); ++path2_idx) {

            auto [distance1, time1, score1] = inputData.EvalVirtualTour(path1, path1.tour.size(),
                    [&](size_t pos) -> points_type {
                        if (pos == path1_idx) return path2.tour[path2_idx];
                        return path1.tour[pos];
                    });
            auto [distance2, time2, score2] = inputData.EvalVirtualTour(path2, path2.tour.size(),
                    [&](size_t pos) -> points_type {
                        if (pos == path2_idx) return path1.tour[path1_idx];
                        return path2.tour[pos];
                    });

            if (distance1 <= path1.max_distance && distance2 <= path2.max_distance && 
                time1 <= path1.max_time && time2 <= path2.max_time && 
                score1 + score2 > initial_score) {

                found = true;
                best_swap = {
                    .path1_idx = path1_idx,
                    .distance1 = distance1,
                    .time1     = time1,
                    .score1    = score1,
                    .path2_idx = path2_idx,
                    .distance2 = distance2,
                    .time2     = time2,
                    .score2    = score2,
                };
                initial_score = score1 + score2;
            }
        }
    }

    if (found) {
        std::swap(path1.tour[best_swap.path1_idx], path2.tour[best_swap.path2_idx]);

        path1.distance = best_swap.distance1;
        path1.time = best_swap.time1;
        path1.score = best_swap.score1;

        path2.distance = best_swap.distance2;
        path2.time = best_swap.time2;
        path2.score = best_swap.score2;
    }

    return found;
}

// обмениваем "хвосты" у двух маршрутов
bool TInterOperations::TwoOpt(TPath& path1, TPath& path2, const TInputData &inputData, TInterOperationContext&) {
    auto initial_score = path1.score + path2.score;

    struct best_operation {
        size_t split1;
        size_t split2;
        int64_t distance1;
        int64_t time1;
        int64_t score1;
        int64_t distance2;
        int64_t time2;
        int64_t score2;
    };

    bool found = false;
    best_operation best_two_opt{};

    // split1 — позиция разреза в path1: хвост path1[split1..] уходит в path2
    // split2 — позиция разреза в path2: хвост path2[split2..] уходит в path1
    for (size_t split1 = 0; split1 < path1.tour.size(); ++split1) {
        for (size_t split2 = 0; split2 < path2.tour.size(); ++split2) {

            const size_t new_size1 = split1 + (path2.tour.size() - split2);
            const size_t new_size2 = split2 + (path1.tour.size() - split1);

            if (new_size1 < path1.min_vertexes || new_size1 > path1.max_vertexes ||
                new_size2 < path2.min_vertexes || new_size2 > path2.max_vertexes) {
                continue;
            }

            auto [distance1, time1, score1] = inputData.EvalVirtualTour(path1, new_size1,
                    [&](size_t pos) -> points_type {
                        if (pos < split1) {
                            return path1.tour[pos];
                        } else {
                            return path2.tour[split2 + (pos - split1)];
                        }
                    });

            auto [distance2, time2, score2] = inputData.EvalVirtualTour(path2, new_size2,
                    [&](size_t pos) -> points_type {
                        if (pos < split2) {
                            return path2.tour[pos];
                        } else {
                            return path1.tour[split1 + (pos - split2)];
                        }
                    });

            if (distance1 <= path1.max_distance && distance2 <= path2.max_distance && 
                time1 <= path1.max_time && time2 <= path2.max_time && 
                score1 + score2 > initial_score) {

                found = true;
                best_two_opt = {
                    .split1    = split1,
                    .split2    = split2,
                    .distance1 = distance1,
                    .time1     = time1,
                    .score1    = score1,
                    .distance2 = distance2,
                    .time2     = time2,
                    .score2    = score2,
                };
                initial_score = score1 + score2;
            }
        }
    }

    if (found) {
        TRoute new_tour1(path1.tour.begin(), path1.tour.begin() + best_two_opt.split1);
        new_tour1.insert(new_tour1.end(), path2.tour.begin() + best_two_opt.split2, path2.tour.end());

        TRoute new_tour2(path2.tour.begin(), path2.tour.begin() + best_two_opt.split2);
        new_tour2.insert(new_tour2.end(), path1.tour.begin() + best_two_opt.split1, path1.tour.end());

        path1.tour = std::move(new_tour1);
        path2.tour = std::move(new_tour2);

        path1.distance = best_two_opt.distance1;
        path1.time     = best_two_opt.time1;
        path1.score    = best_two_opt.score1;
        path2.distance = best_two_opt.distance2;
        path2.time     = best_two_opt.time2;
        path2.score    = best_two_opt.score2;
    }

    return found;
}

// обмениваем у двух маршрутов отрезок
bool TInterOperations::Cross(TPath& path1, TPath& path2, const TInputData &inputData, TInterOperationContext&) {
    auto initial_score = path1.score + path2.score;

    // длина отрезка ограничена четвертью минимального из двух маршрутов
    const size_t max_seg_len = std::min(path1.tour.size(), path2.tour.size()) / 4;
    if (max_seg_len == 0) {
        return false;
    }

    struct best_operation {
        size_t seg_len;
        size_t start1;
        size_t start2;
        int64_t distance1;
        int64_t time1;
        int64_t score1;
        int64_t distance2;
        int64_t time2;
        int64_t score2;
    };

    bool found = false;
    best_operation best_cross{};

    for (size_t seg_len = 1; seg_len <= max_seg_len; ++seg_len) {
        for (size_t start1 = 0; start1 + seg_len <= path1.tour.size(); ++start1) {
            for (size_t start2 = 0; start2 + seg_len <= path2.tour.size(); ++start2) {

                auto [distance1, time1, score1] = inputData.EvalVirtualTour(path1, path1.tour.size(),
                        [&](size_t pos) -> points_type {
                            if (start1 <= pos && pos < start1 + seg_len) {
                                return path2.tour[start2 + (pos - start1)];
                            } else {
                                return path1.tour[pos];
                            }
                        });
                auto [distance2, time2, score2] = inputData.EvalVirtualTour(path2, path2.tour.size(),
                        [&](size_t pos) -> points_type {
                            if (start2 <= pos && pos < start2 + seg_len) {
                                return path1.tour[start1 + (pos - start2)];
                            } else {
                                return path2.tour[pos];
                            }
                        });

                if (distance1 <= path1.max_distance && distance2 <= path2.max_distance && 
                    time1 <= path1.max_time && time2 <= path2.max_time && 
                    score1 + score2 > initial_score) {
    
                    found = true;
                    best_cross = {
                        .seg_len   = seg_len,
                        .start1    = start1,
                        .start2    = start2,
                        .distance1 = distance1,
                        .time1     = time1,
                        .score1    = score1,
                        .distance2 = distance2,
                        .time2     = time2,
                        .score2    = score2,
                    };
                    initial_score = score1 + score2;
                }
            }
        }
    }

    if (found) {
        std::swap_ranges(
            path1.tour.begin() + best_cross.start1,
            path1.tour.begin() + best_cross.start1 + best_cross.seg_len,
            path2.tour.begin() + best_cross.start2
        );

        path1.distance = best_cross.distance1;
        path1.time     = best_cross.time1;
        path1.score    = best_cross.score1;
        path2.distance = best_cross.distance2;
        path2.time     = best_cross.time2;
        path2.score    = best_cross.score2;
    }

    return found;
}

// обмениваем отрезок между отрезками
bool TInterOperations::RelocateSegment(TPath& path1, TPath& path2, const TInputData &inputData, TInterOperationContext&) {
    auto initial_score = path1.score + path2.score;

    struct best_operation {
        bool from_first;
        size_t from_idx;
        size_t to_idx;
        int64_t src_distance;
        int64_t src_time;
        int64_t src_score;
        int64_t dst_distance;
        int64_t dst_time;
        int64_t dst_score;
        size_t seg_len;
    };

    bool found = false;
    best_operation best{};

    // src -> dst: пробуем переместить отрезок из src в dst и ищем лучший вариант
    auto try_relocate_direction = [&](TPath& src, TPath& dst, bool from_first) {
        if (src.tour.size() <= src.min_vertexes || dst.tour.size() >= dst.max_vertexes) {
            return;
        }

        const size_t max_seg_len = std::min(src.tour.size() - src.min_vertexes, dst.max_vertexes - dst.tour.size());

        for (size_t seg_len = 1; seg_len <= max_seg_len; ++seg_len) {

            for (size_t from = 0; from + seg_len <= src.tour.size(); ++from) {

                auto [distance1, time1, score1] = inputData.EvalVirtualTour(src, src.tour.size() - seg_len,
                        [&](size_t pos) -> points_type {
                            if (pos < from) {
                                return src.tour[pos];
                            } else {
                                return src.tour[pos + seg_len];
                            }
                        });

                for (size_t to = 0; to <= dst.tour.size(); ++to) {

                    auto [distance2, time2, score2] = inputData.EvalVirtualTour(dst, dst.tour.size() + seg_len,
                            [&](size_t pos) -> points_type {
                                if (to <= pos && pos < to + seg_len) {
                                    return src.tour[from + (pos - to)];
                                } else if (pos < to) {
                                    return dst.tour[pos];
                                } else {
                                    return dst.tour[pos - seg_len];
                                }
                            });
                    
                    if (distance1 <= src.max_distance && distance2 <= dst.max_distance &&
                        time1 <= src.max_time && time2 <= dst.max_time &&
                        score1 + score2 > initial_score) {

                        found = true;
                        best = {
                            .from_first   = from_first,
                            .from_idx     = from,
                            .to_idx       = to,
                            .src_distance = distance1,
                            .src_time     = time1,
                            .src_score    = score1,
                            .dst_distance = distance2,
                            .dst_time     = time2,
                            .dst_score    = score2,
                            .seg_len      = seg_len,
                        };
                        initial_score = score1 + score2;
                    }
                }
            }
        }
    };

    try_relocate_direction(path1, path2, true);
    try_relocate_direction(path2, path1, false);

    if (found) {
        TPath& src = best.from_first ? path1 : path2;
        TPath& dst = best.from_first ? path2 : path1;

        std::vector<TRoute::value_type> segment(src.tour.begin() + best.from_idx, src.tour.begin() + best.from_idx + best.seg_len);

        src.tour.erase(src.tour.begin() + best.from_idx, src.tour.begin() + best.from_idx + best.seg_len);
        dst.tour.insert(dst.tour.begin() + best.to_idx, segment.begin(), segment.end());

        src.distance = best.src_distance;
        src.time = best.src_time;
        src.score = best.src_score;
        dst.distance = best.dst_distance;
        dst.time = best.dst_time;
        dst.score = best.dst_score;
    }

    return found;
}

// cклейка и разрез двух маршрутов
bool TInterOperations::Glue(TPath& path1, TPath& path2, const TInputData &inputData, TInterOperationContext& ctx) {
    int64_t initial_score = path1.score + path2.score;
    if (path1.tour.size() < path1.min_vertexes || path2.tour.size() < path2.min_vertexes) {
        initial_score = std::numeric_limits<int64_t>::min();
    }

    const size_t combined_size = path1.tour.size() + path2.tour.size();
    if (combined_size == 0) {
        return false;
    }

    if (combined_size < path1.min_vertexes + path2.min_vertexes) {
        return false;
    }

    TRoute combined;
    combined.reserve(path1.tour.size() + path2.tour.size());
    combined.insert(combined.end(), path1.tour.begin(), path1.tour.end());
    combined.insert(combined.end(), path2.tour.begin(), path2.tour.end());

    TPath temp;
    temp.tour = std::move(combined);
    temp.depo = path1.depo;
    temp.agent_idx = path1.agent_idx;
    temp.max_distance = std::numeric_limits<decltype(temp.max_distance)>::max();
    temp.max_time = std::numeric_limits<decltype(temp.max_time)>::max();
    temp.max_vertexes = static_cast<decltype(temp.max_vertexes)>(combined_size);
    temp.min_vertexes = 0;
    std::tie(temp.distance, temp.time, temp.score) = inputData.EvalVirtualTour(
        temp, temp.tour.size(),
        [&](size_t pos) -> points_type { return temp.tour[pos]; });

    OptimizationContext inner_ctx;
    inner_ctx.inner_preserve_vertex_set = true;
    inner_ctx.inner_iterations_without_improve = ctx.max_glue_inner_optimization_iterations;
    inner_ctx.take_first_improve = false;

    TOperatorSelector selector;
    selector.Init(inputData.agents_count);
    DoInnerOptimization(temp, inputData, inner_ctx, selector);

    const size_t min_split = path1.min_vertexes;
    const size_t max_split = std::min<size_t>(path1.max_vertexes, combined_size - path2.min_vertexes);
    if (min_split > max_split) {
        return false;
    }

    struct best_operation {
        size_t split;
        int64_t first_time;
        int64_t first_score;
        int64_t first_distance;
        int64_t second_time;
        int64_t second_score;
        int64_t second_distance;
    };


    bool found = false;
    best_operation best_glue{};

    for (size_t split = min_split; split <= max_split; ++split) {
        const size_t second_size = combined_size - split;
        if (second_size < path2.min_vertexes || second_size > path2.max_vertexes) {
            continue;
        }
        auto [d1, t1, s1] = inputData.EvalVirtualTour(path1, split, [&](size_t pos) -> points_type {
            return temp.tour[pos];
        });
        if (d1 > path1.max_distance || t1 > path1.max_time) {
            continue;
        }
        auto [d2, t2, s2] = inputData.EvalVirtualTour(path2, second_size, [&](size_t pos) -> points_type {
            return temp.tour[split + pos];
        });
        if (d2 > path2.max_distance || t2 > path2.max_time) {
            continue;
        }
        if (s1 + s2 > initial_score) {
            found = true;
            best_glue = {
                .split = split,
                .first_time = t1,
                .first_score = s1,
                .first_distance = d1,
                .second_time = t2,
                .second_score = s2,
                .second_distance = d2,
            };
            initial_score = s1 + s2;
        }
    }

    if (!found) {
        return false;
    }

    path1.tour.assign(temp.tour.begin(), temp.tour.begin() + best_glue.split);
    path2.tour.assign(temp.tour.begin() + best_glue.split, temp.tour.end());
    path1.distance = best_glue.first_distance;
    path1.time = best_glue.first_time;
    path1.score = best_glue.first_score;
    path2.distance = best_glue.second_distance;
    path2.time = best_glue.second_time;
    path2.score = best_glue.second_score;
    return true;
}
