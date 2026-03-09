#include "problem_arguments.hpp"
#include <unistd.h>
#include <ostream>

#ifdef DEBUG
#include "debug.h"
#endif

bool ParseProgramArguments(int argc, char *argv[], ProgramArguments &args) {
    int opt;
    args.save_csv = false;
    
    // Значения по умолчанию для мета-параметров
    args.meta.population_size = 20;
    args.meta.alpha = 15;
    args.meta.beta = 0.2;
    args.meta.nloop = 20;
    args.meta.kMax = 10;
    args.meta.p = 0.1;
    args.meta.max_iter_without_solution = 15;
    args.meta.max_crossover_candidates = 3;
    
    while ((opt = getopt(argc, argv, "p:s:t:c:o:a:b:n:k:g:i:r:")) != -1) {
        switch (opt) {
            case 'p': {
                args.problemJsonPath = optarg;
                break;
            }
            case 's': {
                args.solutionJsonPath = optarg;
                break;
            }
            case 't': {
                args.time = std::stoull(optarg);
                break;
            }
            case 'c': {
                args.csv_file = optarg;
                args.save_csv = true;
                break;
            }
            case 'o': {
                args.meta.population_size = std::stoul(optarg);
                break;
            }
            case 'a': {
                args.meta.alpha = std::stoul(optarg);
                break;
            }
            case 'b': {
                args.meta.beta = static_cast<float>(std::stoul(optarg)) / 10.f;
                break;
            }
            case 'n': {
                args.meta.nloop = std::stoul(optarg);
                break;
            }
            case 'k': {
                args.meta.kMax = std::stoul(optarg);
                break;
            }
            case 'g': {
                args.meta.p = static_cast<float>(std::stoul(optarg)) / 10.f;
                break;
            }
            case 'i': {
                args.meta.max_iter_without_solution = std::stoul(optarg);
                break;
            }
            case 'r': {
                args.meta.max_crossover_candidates = std::stoul(optarg);
                break;
            }
            default: {
                return false;
            }
        }
    }
#ifdef DEBUG
    std::cout << "Problem path: " << args.problemJsonPath
              << " solution path: " << args.solutionJsonPath 
              << " time: " << args.time << std::endl;
#endif

    return true;
}

int64_t InputData::get_time_dependent_cost(int64_t time,
                                           InputData::points_type from,
                                           InputData::points_type to) const {

    if (is_mapped) {
        from = from_new_to_old.at(from);
        to = from_new_to_old.at(to);
    }
                                            
    if (time >= time_duration * (time_matrix.size() - 1)) {
        return time_matrix[time_matrix.size() - 1][from][to];
    }

    const auto time_matrix_idx = time / time_duration;
    const long double alpha = static_cast<long double>(time - time_duration * time_matrix_idx) / time_duration;

    return static_cast<int64_t>((1 - alpha) * time_matrix[time_matrix_idx][from][to] +
                                alpha * time_matrix[time_matrix_idx + 1][from][to]);
}

std::tuple<int64_t, int64_t, int64_t>
InputData::get_path_time_distance_score(const std::vector<InputData::points_type> &path) const {

    if (path.size() <= 2) {
        return std::make_tuple(0, 0, 0);
    }

    int64_t distance = 0;
    int64_t time = 0;
    int64_t score = 0;

    // считаем время и дистанцию с учетом времени обслуживания точек
    // i -> i + 1
    // 0 -> 1
    // 1 -> 2
    // ...
    // n -> 0
    points_type from = 0, to = 0;
    for (size_t i = 0; i < path.size() - 1; ++i) {

        if (is_mapped) {
            from = from_new_to_old.at(path[i]);
            to = from_new_to_old.at(path[i + 1]);
        } else {
            from = path[i];
            to = path[i + 1];
        }

        distance += distance_matrix[from][to];
        // функция сама сделает маппинг если is_mapped
        auto travel_time = get_time_dependent_cost(time + agent_start_time[current_agent], path[i], path[i + 1]);

        time += (to == 0 ? 0 : point_service_times[to - 1]) + travel_time;
        // point_scores - свдинуты на 1 индекс, т.к. 0 - депо
        score += (to == 0 ? 0 : point_scores[to - 1]) - travel_time;
    }

    return std::make_tuple(distance, time, score);
}

std::ostream &operator<<(std::ostream &os, const InputData &data) {
    os << "points_count: " << data.points_count << "\n";

    os << "Agents info:\n";
    for (size_t i = 0; i < data.agents_count; ++i) {
        os << "\tAgent #" << i << " "
        << "min_load: " << data.min_load[i] << " "
        << "max_load: " << data.max_load[i] << " "
        << "max_time: " << data.max_time[i] << " "
        << "max_distance: " << data.max_distance[i] << "\n";
    }

    os << "point_scores: ";
    for (auto val: data.point_scores) {
        os << val << " ";
    }
    os << "\n";

    return os;
}

std::ostream &operator<<(std::ostream &os, const OutData &solution) {
    os << "solution_size: " << solution.solution_size << "\n";

    os << "route: ";
    for (auto idx: solution.route) {
        os << idx << " ";
    }
    os << "\n";

    os << "total_time: " << solution.total_time << "\n";
    os << "total_distance: " << solution.total_distance << "\n";
    os << "total_value: " << solution.total_value << "\n";

    return os;
}