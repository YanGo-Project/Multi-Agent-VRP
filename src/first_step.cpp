#include "../include/first_step.hpp"

#include <algorithm>
#include <iostream>
#include <limits>
#include <bitset>

constexpr size_t TOP_SOLUTIONS_COUNT = 7;

namespace {
    using score_type = FirstStepAnswer::score_type;
    using points_type = FirstStepAnswer::points_type;

    template <size_t bitset_size = std::numeric_limits<points_type>::max()>
    struct Candidate {
        static constexpr size_t MAX_POINTS = bitset_size;

        // посещения в пути, вершина с индексом i лежит в ячейке visited[i],
        // чтобы не было коллизий с депо
        std::bitset<MAX_POINTS> visited;

        // информация о метриках
        score_type value;
        score_type time;
        score_type distance;

        int64_t load;

        // для восстановления из dp[cur_load][last_vertex][candidate_idx]
        size_t candidate_idx;
        points_type last_vertex;

        inline bool IsVertexInPath(const points_type id) const {
            return visited[id];
        }

        FirstStepAnswer CreateAnswer(const std::vector<std::vector<std::vector<Candidate<bitset_size>>>>& dp, const points_type depo) const {
            FirstStepAnswer answer;
            answer.vertexes.reserve(visited.count());
            answer.value = value;
            answer.time = time;
            answer.distance = distance;

            auto next_load = load;
            auto next_vertex = last_vertex;
            auto next_candidate_idx = candidate_idx;

            while (next_load >= 0) {

                if (next_vertex != depo) {
                    answer.vertexes.push_back(next_vertex);
                }
                const auto& cand = dp[next_load][next_vertex][next_candidate_idx];

                next_load -= 1;
                next_vertex = cand.last_vertex;
                next_candidate_idx = cand.candidate_idx;
            }

            std::reverse(answer.vertexes.begin(), answer.vertexes.end());

            return answer; // RVO 
        }
    };

    template <size_t bitset_size>
    inline bool IsCandidateGood(const std::vector<Candidate<bitset_size>>& candidates, score_type value) {
        if (candidates.empty() || candidates.size() < TOP_SOLUTIONS_COUNT) [[unlikely]] {
            return true;
        }

        return value > candidates.back().value;
    }
    
    template <size_t bitset_size>
    inline void InsertTopCandidate(std::vector<Candidate<bitset_size>>& candidates, Candidate<bitset_size>&& newCandidate) {

        bool duplicated = false;
        for (auto& existed_candidate : candidates) {
            if (existed_candidate.visited == newCandidate.visited) {
                if (existed_candidate.value < newCandidate.value) {
                    std::swap(existed_candidate, newCandidate);
                } else {
                    // уже есть такой путь и у него score лучше
                    return;
                }
                duplicated = true;
                break;
            }
        }

        if (!duplicated) {
            candidates.emplace_back(std::move(newCandidate));
        }

        std::sort(candidates.begin(), candidates.end(), 
            [](const auto& first, const auto& second) {
                return first.value > second.value;
            }    
        );

        if (candidates.size() == TOP_SOLUTIONS_COUNT + 1) [[likely]] {
            candidates.resize(TOP_SOLUTIONS_COUNT);
        }
    }

}

template<size_t bitset_size, bool is_time_dependent>
std::vector<FirstStepAnswer> DoFirstStep(const TInputData &input, const size_t agent) {

    using score_type = FirstStepAnswer::score_type;
    using points_type = FirstStepAnswer::points_type;

    auto start_time = input.agent_start_time[agent];
    auto max_dist = input.max_distance[agent];
    auto max_time = input.max_time[agent];
    auto max_load = input.max_load[agent];
    auto min_load = input.min_load[agent];
    auto points_count = input.points_count;

    // dp теперь хранит векторы сжатых представлений решений для каждого состояния
    std::vector<std::vector<std::vector<Candidate<bitset_size>>>> dp(
        max_load + 2,
        std::vector<std::vector<Candidate<bitset_size>>>(points_count)
    );

    // депо текущего агента
    const auto agent_depo = input.agent_depots[agent];

    // инициализация начального состояния
    Candidate<bitset_size> initial;
    initial.value = 0;
    initial.time = 0;
    initial.distance = 0;
    initial.load = -1;
    dp[0][agent_depo].push_back(std::move(initial));


    std::vector<Candidate<bitset_size>> candidates;
    candidates.reserve(TOP_SOLUTIONS_COUNT);

    for (points_type cur_load = 0; cur_load <= max_load; ++cur_load) {
        bool find_update_point = false;
    
        // строим путь который будет заканичваться в вершине to_vertex
        for (points_type to_vertex = 0; to_vertex < points_count; ++to_vertex) {

            candidates.clear();

            // пропускаем все депо, если это не депо нашего агента
            if (to_vertex != agent_depo && input.depots_set.find(to_vertex) != input.depots_set.end()) {
                continue;
            }

            // последняя вершина в пути
            for (points_type last_vertex = 0; last_vertex < points_count; ++last_vertex) {

                // пропускаем все депо, если это не депо нашего агента
                if (last_vertex != agent_depo && input.depots_set.find(last_vertex) != input.depots_set.end()) {
                    continue;
                }

                // хотим искать пути из депо только если загрузка 0 (первое ребро в пути)
                if (last_vertex == agent_depo && cur_load != 0) [[unlikely]] {
                    continue;
                }

                // делаем проверку:
                // 1. вершины не совпали   
                // 2. есть такой путь с cur_load вершинами, который заканчивается в last_vertex
                if (last_vertex != to_vertex && !dp[cur_load][last_vertex].empty()) [[likely]] {

                    // перебираем все решения из dp[cur_load][last_vertex]
                    for (size_t candidate_idx = 0; candidate_idx < dp[cur_load][last_vertex].size(); ++candidate_idx) {
                        const auto& prev_solution = dp[cur_load][last_vertex][candidate_idx];

                        // 3. вершина to_vertex еще не была в пути
                        // 4. вершина to_vertex еше не была посещена в пути другого агента
                        if (prev_solution.value != FirstStepAnswer::default_value &&
                            !prev_solution.IsVertexInPath(to_vertex) &&
                            (to_vertex == agent_depo || input.visited_points.find(to_vertex) == input.visited_points.end())
                        ) [[likely]] {

                            FirstStepAnswer::score_type travel_time;
                            if constexpr (is_time_dependent) {
                                travel_time = input.get_time_dependent_cost(prev_solution.time + start_time, last_vertex, to_vertex);
                            } else {
                                travel_time = input.time_matrix[0][last_vertex][to_vertex];
                            }

                            auto new_point_score = prev_solution.value + input.point_scores[to_vertex] - travel_time;
                            auto new_point_time = prev_solution.time + input.point_service_times[to_vertex - 1] + travel_time;
                            auto new_point_dist = prev_solution.distance + input.distance_matrix[last_vertex][to_vertex];

                            // проверки найденного пути на целевую функцию, максимальное время пути и максимальную дистанцию
                            if (new_point_time <= max_time &&
                                new_point_dist <= max_dist && 
                                IsCandidateGood(candidates, new_point_score)
                            ) {
                                auto new_visited = prev_solution.visited;
                                if (to_vertex != agent_depo) {
                                    new_visited.set(to_vertex);
                                }
                                InsertTopCandidate(
                                    candidates,
                                    Candidate<bitset_size> {
                                        .visited = std::move(new_visited),
                                        .value = new_point_score,
                                        .time = new_point_time,
                                        .distance = new_point_dist,
                                        .load = cur_load,
                                        .candidate_idx = candidate_idx,
                                        .last_vertex = last_vertex
                                    }
                                );
                            }
                        }
                    }
                }
            }

            if (!candidates.empty()) [[likely]] {
                dp[cur_load + 1][to_vertex] = std::move(candidates);
                find_update_point = true;
            }
        }

        if (!find_update_point) {
            // выходим если не смогли обновить ни один из путей для cur_load + 1
            break;
        }
    }

    // собираем все лучшие решения из всех допустимых состояний
    std::vector<Candidate<bitset_size>> answer_candidates;
    answer_candidates.reserve(TOP_SOLUTIONS_COUNT);

    for (points_type cur_load = min_load + 1; cur_load <= max_load + 1; ++cur_load) {
        for (auto& candidate : dp[cur_load][agent_depo]) {
            if (IsCandidateGood(answer_candidates, candidate.value)) {
                InsertTopCandidate(answer_candidates, std::move(candidate));
            }
        }
    }

    std::vector<FirstStepAnswer> answer_solutions;
    answer_solutions.reserve(answer_candidates.size());

    // восстанавливаем лучшие решения из кандидатов
    for (const auto& candidate: answer_candidates) {
        answer_solutions.emplace_back(candidate.CreateAnswer(dp, agent_depo));
    }
    return answer_solutions;
}

std::ostream &operator<<(std::ostream &os, const FirstStepAnswer &answer) {
    os << "Solution score value: " << answer.value << std::endl;
    os << "Solution path:\n";
    for (auto id: answer.vertexes) {
        os << id << " ";
    }
    os << "\nSolution time: " << answer.time << "\nSolution distance: " << answer.distance << "\nSolution size: "
       << answer.vertexes.size();
    os << std::endl;

    return os;
}

template std::vector<FirstStepAnswer> DoFirstStep<128, true>(const TInputData &input, const size_t agent);
template std::vector<FirstStepAnswer> DoFirstStep<256, true>(const TInputData &input, const size_t agent);
template std::vector<FirstStepAnswer> DoFirstStep<512, true>(const TInputData &input, const size_t agent);
template std::vector<FirstStepAnswer> DoFirstStep<std::numeric_limits<TInputData::points_type>::max(), true>(const TInputData &input, const size_t agent);


template std::vector<FirstStepAnswer> DoFirstStep<128, false>(const TInputData &input, const size_t agent);
template std::vector<FirstStepAnswer> DoFirstStep<256, false>(const TInputData &input, const size_t agent);
template std::vector<FirstStepAnswer> DoFirstStep<512, false>(const TInputData &input, const size_t agent);
template std::vector<FirstStepAnswer> DoFirstStep<std::numeric_limits<TInputData::points_type>::max(), false>(const TInputData &input, const size_t agent);