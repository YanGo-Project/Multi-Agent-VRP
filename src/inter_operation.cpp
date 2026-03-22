#include "../include/inter_operation.hpp"

#include <algorithm>
#include <cassert>
#include <cstring>
#include <iomanip>
#include <iostream>

std::ostream& operator<<(std::ostream& os, const TPath& path) {
    os << "score=" << std::setw(8) << path.score
       << "  time=" << std::setw(8) << path.time
       << "  dist=" << std::setw(8) << path.distance
       << "  stops=" << path.tour.size() << "\n";
    os << "  route: [depo]";
    for (auto v : path.tour) {
        os << " -> " << v;
    }
    os << " -> [depo]\n";
    return os;
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

                if (distance1 > src.max_distance || distance2 > dst.max_distance) {
                    ++stats.dist_exceed;
                } else if (time1 > src.max_time || time2 > dst.max_time) {
                    ++stats.time_exceed;
                } else if (score1 + score2 <= initial_score) {
                    ++stats.no_gain;
                } else {
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

#ifdef DEBUG_SWAP
    int debug_printed = 0;
    int kDebugMaxPrint = 5;
    std::cout << "[DebugSwap] path1: time=" << path1.time << "/" << path1.max_time
              << "  slack=" << (path1.max_time - path1.time)
              << "  path2: time=" << path2.time << "/" << path2.max_time
              << "  slack=" << (path2.max_time - path2.time) << "\n";
#endif

    for (size_t path1_idx = 0; path1_idx < path1.tour.size(); ++path1_idx) {
        for (size_t path2_idx = 0; path2_idx < path2.tour.size(); ++path2_idx) {

            const auto v1 = path1.tour[path1_idx];
            const auto v2 = path2.tour[path2_idx];

            std::swap(path1.tour[path1_idx], path2.tour[path2_idx]);

            auto [distance1, time1, score1] = inputData.get_path_distance_time_score(path1);
            auto [distance2, time2, score2] = inputData.get_path_distance_time_score(path2);

#ifdef DEBUG_SWAP
                const auto slack1 = path1.max_time - path1.time;
                const auto slack2 = path2.max_time - path2.time;
                const char* reason = "OK";
                if (distance1 >= path1.max_distance || distance2 >= path2.max_distance) reason = "dist_exceed";
                else if (time1 >= path1.max_time || time2 >= path2.max_time)             reason = "time_exceed";
                else if (score1 + score2 <= initial_score)                               reason = "no_gain";
                if (debug_printed < kDebugMaxPrint || strcmp(reason, "OK") == 0) {
                    std::cout << "[DebugSwap]   swap v1=" << v1 << "@pos" << path1_idx
                              << " <-> v2=" << v2 << "@pos" << path2_idx
                              << " | p1: " << path1.time << "->" << time1
                              << " (slack было " << slack1 << ", стало " << (path1.max_time - time1) << ")"
                              << " | p2: " << path2.time << "->" << time2
                              << " (slack было " << slack2 << ", стало " << (path2.max_time - time2) << ")"
                              << " | " << reason << "\n";
                    ++debug_printed;
                }
#endif

            if (distance1 >= path1.max_distance || distance2 >= path2.max_distance) {
                ++stats.dist_exceed;
            } else if (time1 >= path1.max_time || time2 >= path2.max_time) {
                ++stats.time_exceed;
            } else if (score1 + score2 <= initial_score) {
                ++stats.no_gain;
            } else {
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

            if (distance1 > path1.max_distance || distance2 > path2.max_distance) {
                ++stats.dist_exceed;
            } else if (time1 > path1.max_time || time2 > path2.max_time) {
                ++stats.time_exceed;
            } else if (score1 + score2 <= initial_score) {
                ++stats.no_gain;
            } else {
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

                if (distance1 > path1.max_distance || distance2 > path2.max_distance) {
                    ++stats.dist_exceed;
                } else if (time1 > path1.max_time || time2 > path2.max_time) {
                    ++stats.time_exceed;
                } else if (score1 + score2 <= initial_score) {
                    ++stats.no_gain;
                } else {
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

void TInterOperations::RunLocalSearch(std::vector<TPath>& paths,
                                      const TInputData&   inputData,
                                      int                 max_no_improvement) {
    assert(max_no_improvement > 0);

    static constexpr TOperationFn kOperations[] = {
        &TInterOperations::Relocate,
        &TInterOperations::Swap,
        &TInterOperations::TwoOpt,
        &TInterOperations::Cross,
    };
    static constexpr const char* kOperationNames[] = {
        "Relocate", "Swap", "TwoOpt", "Cross",
    };
    static constexpr int kOperationsCount = static_cast<int>(std::size(kOperations));

    std::mt19937 rng{std::random_device{}()};
    std::uniform_int_distribution<size_t> path_dist(0, paths.size() - 1);
    std::uniform_int_distribution<int>    op_dist(0, kOperationsCount - 1);

    int no_improvement_streak = 0;
    int total_attempts        = 0;
    int total_improvements    = 0;

    // статистика улучшений по каждой операции
    int op_improvements[kOperationsCount] = {};

    std::cout << "[LocalSearch] start  total_score="
              << [&] {
                     int64_t s = 0;
                     for (auto& p : paths) s += p.score;
                     return s;
                 }()
              << "  K=" << max_no_improvement << "\n";

    while (no_improvement_streak < max_no_improvement) {
        size_t i = path_dist(rng);
        size_t j = path_dist(rng);
        while (j == i) {
            j = path_dist(rng);
        }

        const int     op_idx      = op_dist(rng);
        const int64_t score_before = paths[i].score + paths[j].score;

        RejectStats stats{};
        const bool improved = (this->*kOperations[op_idx])(paths[i], paths[j], inputData, stats);
        ++total_attempts;

        if (improved) {
            const int64_t score_after = paths[i].score + paths[j].score;
            const int64_t delta       = score_after - score_before;

            ++total_improvements;
            ++op_improvements[op_idx];
            no_improvement_streak = 0;

            std::cout << "[LocalSearch] #" << std::setw(4) << total_attempts
                      << "  " << std::setw(8) << std::left << kOperationNames[op_idx] << std::right
                      << "  agents=(" << i << "," << j << ")"
                      << "  delta=" << std::showpos << delta << std::noshowpos
                      << "  score_after=" << score_after
                      << "  streak_reset\n";
        } else {
            ++no_improvement_streak;

#ifdef DEBUG_LOCAL_SEARCH
            std::cout << "[LocalSearch] #" << std::setw(4) << total_attempts
                      << "  " << std::setw(8) << std::left << kOperationNames[op_idx] << std::right
                      << "  agents=(" << i << "," << j << ")"
                      << "  FAIL"
                      << "  vertex_limit=" << stats.vertex_limit
                      << "  time_exceed="  << stats.time_exceed
                      << "  dist_exceed="  << stats.dist_exceed
                      << "  no_gain="      << stats.no_gain
                      << "  streak=" << no_improvement_streak << "/" << max_no_improvement << "\n";
#endif        
        }
    }

    // итоговая статистика
    int64_t total_score = 0;
    for (auto& p : paths) total_score += p.score;

    std::cout << "[LocalSearch] done"
              << "  attempts="    << total_attempts
              << "  improvements=" << total_improvements
              << "  total_score=" << total_score << "\n";
    std::cout << "[LocalSearch] improvements by operation:\n";
    for (int k = 0; k < kOperationsCount; ++k) {
        std::cout << "    " << std::setw(8) << std::left << kOperationNames[k] << std::right
                  << " : " << op_improvements[k] << "\n";
    }
}
