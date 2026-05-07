#pragma once

#include "problem_arguments.hpp"
#include "../include/path.hpp"

// get_vertex(i) -> points_type  — возвращает i-ю клиентскую вершину виртуального тура.
// tour_size —> число клиентских вершин.
template<typename GetVertex>
std::tuple<int64_t, int64_t, int64_t>
TInputData::EvalVirtualTour(const TPath& path, size_t tour_size, GetVertex&& get_vertex) const {
    if (tour_size == 0) {
        return {0, 0, 0};
    }

    int64_t distance = 0, time = 0, score = 0;
    const auto start_depo = path.start_depo;
    const auto end_depo = path.end_depo;
    const int64_t start_time = agent_start_time[path.agent_idx];

    points_type from = start_depo;
    for (size_t i = 0; i <= tour_size; ++i) {
        const points_type to = (i == tour_size) ? end_depo : get_vertex(i);

        distance += distance_matrix[from][to];
        const auto travel = get_time_dependent_cost(time + start_time, from, to);
        time  += point_service_times[to] + travel;
        score += point_scores[to] - travel;

        from = to;
    }
    return {distance, time, score};
}
