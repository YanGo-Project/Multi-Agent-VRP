#include "../include/inter_operation.hpp"

#include <algorithm>
#include <cassert>
#include <cstring>
#include <iomanip>
#include <iostream>

bool TInterOperations::DoOperation(TPath& path1, TPath& path2, const TInputData& inputData,
                                   EInterOperation operation) {
    static constexpr TOperationFn kOperations[] = {
        &TInterOperations::Relocate,    // 0
        &TInterOperations::Swap,        // 1
        &TInterOperations::TwoOpt,      // 2
        &TInterOperations::Cross,       // 3
    };
    static constexpr uint8_t kOperationsSize =
        static_cast<uint8_t>(sizeof(kOperations) / sizeof(kOperations[0]));

    const uint8_t idx = static_cast<uint8_t>(operation);
    assert(idx < kOperationsSize);
    if (idx >= kOperationsSize) {
        return false;
    }

    RejectStats stats{};
    return (this->*kOperations[idx])(path1, path2, inputData, stats);
}

bool TInterOperations::Relocate(TPath& path1, TPath& path2, const TInputData &inputData, RejectStats& stats) {
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
    };

    bool found = false;
    best_operation best_relocation{};

    // src -> dst: пробуем переместить вершину из src в dst и ищем лучший вариант
    auto try_relocate_direction = [&](TPath& src, TPath& dst, bool from_first) {
        if (src.tour.size() <= src.min_vertexes || dst.tour.size() >= dst.max_vertexes) {
            ++stats.vertex_limit;
            return;
        }

        for (size_t from = 0; from < src.tour.size(); ++from) {
            const auto element = src.tour[from];
            src.tour.erase(src.tour.begin() + from);
            auto [distance1, time1, score1] = inputData.get_path_distance_time_score(src);

            for (size_t to = 0; to <= dst.tour.size(); ++to) {
                dst.tour.insert(dst.tour.begin() + to, element);

                auto [distance2, time2, score2] = inputData.get_path_distance_time_score(dst);
                
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

                dst.tour.erase(dst.tour.begin() + to);
            }

            src.tour.insert(src.tour.begin() + from, element);
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

bool TInterOperations::Swap(TPath& path1, TPath& path2, const TInputData &inputData, RejectStats& stats) {
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

            const auto v1 = path1.tour[path1_idx];
            const auto v2 = path2.tour[path2_idx];

            std::swap(path1.tour[path1_idx], path2.tour[path2_idx]);

            auto [distance1, time1, score1] = inputData.get_path_distance_time_score(path1);
            auto [distance2, time2, score2] = inputData.get_path_distance_time_score(path2);

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

            // возврат путей к исходному состоянию
            std::swap(path1.tour[path1_idx], path2.tour[path2_idx]);
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

bool TInterOperations::TwoOpt(TPath& path1, TPath& path2, const TInputData &inputData, RejectStats& stats) {
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
    for (size_t split1 = 0; split1 <= path1.tour.size(); ++split1) {
        for (size_t split2 = 0; split2 <= path2.tour.size(); ++split2) {

            const size_t new_size1 = split1 + (path2.tour.size() - split2);
            const size_t new_size2 = split2 + (path1.tour.size() - split1);

            if (new_size1 < path1.min_vertexes || new_size1 > path1.max_vertexes ||
                new_size2 < path2.min_vertexes || new_size2 > path2.max_vertexes) {
                ++stats.vertex_limit;
                continue;
            }

            TRoute new_tour1(path1.tour.begin(), path1.tour.begin() + split1);
            new_tour1.insert(new_tour1.end(), path2.tour.begin() + split2, path2.tour.end());

            TRoute new_tour2(path2.tour.begin(), path2.tour.begin() + split2);
            new_tour2.insert(new_tour2.end(), path1.tour.begin() + split1, path1.tour.end());

            std::swap(path1.tour, new_tour1);
            std::swap(path2.tour, new_tour2);

            auto [distance1, time1, score1] = inputData.get_path_distance_time_score(path1);
            auto [distance2, time2, score2] = inputData.get_path_distance_time_score(path2);

            // возврат к исходному состоянию
            std::swap(path1.tour, new_tour1);
            std::swap(path2.tour, new_tour2);

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

bool TInterOperations::Cross(TPath& path1, TPath& path2, const TInputData &inputData, RejectStats& stats) {
    auto initial_score = path1.score + path2.score;

    // длина отрезка ограничена четвертью минимального из двух маршрутов
    const size_t max_seg_len = std::min(path1.tour.size(), path2.tour.size()) / 4;
    if (max_seg_len == 0) {
        ++stats.vertex_limit;
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

                std::swap_ranges(
                    path1.tour.begin() + start1,
                    path1.tour.begin() + start1 + seg_len,
                    path2.tour.begin() + start2
                );

                auto [distance1, time1, score1] = inputData.get_path_distance_time_score(path1);
                auto [distance2, time2, score2] = inputData.get_path_distance_time_score(path2);

                // возврат к исходному состоянию
                std::swap_ranges(
                    path1.tour.begin() + start1,
                    path1.tour.begin() + start1 + seg_len,
                    path2.tour.begin() + start2
                );

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
