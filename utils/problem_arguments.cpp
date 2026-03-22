#include "problem_arguments.hpp"
#include "../include/path.hpp"
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

int64_t TInputData::get_time_dependent_cost(int64_t time,
                                           TInputData::points_type from,
                                           TInputData::points_type to) const {

                                            
    if (time >= time_duration * (time_matrix.size() - 1)) {
        return time_matrix[time_matrix.size() - 1][from][to];
    }

    const auto time_matrix_idx = time / time_duration;
    const long double alpha = static_cast<long double>(time - time_duration * time_matrix_idx) / time_duration;

    return static_cast<int64_t>((1 - alpha) * time_matrix[time_matrix_idx][from][to] +
                                alpha * time_matrix[time_matrix_idx + 1][from][to]);
}

std::tuple<int64_t, int64_t, int64_t>
TInputData::get_path_distance_time_score(const TPath& path) const {

    if (path.tour.empty()) {
        return {0, 0, 0};
    }

    int64_t distance = 0;
    int64_t time = 0;
    int64_t score = 0;

    const auto depo = path.depo;

    points_type from = depo, to = 0;
    for (size_t i = 0; i < path.tour.size() + 1; ++i) {
        
        if (i == path.tour.size()) [[unlikely]] {
            to = depo;
        } else {
            to = path.tour[i];
        }

        distance += distance_matrix[from][to];
        auto travel_time = get_time_dependent_cost(time + agent_start_time[path.agent_idx], from, to);
        time += (to == depo ? 0 : point_service_times[to - 1]) + travel_time;
        score += (to == depo ? 0 : point_scores[to - 1]) - travel_time;

        from = to;
    }

    return std::make_tuple(distance, time, score);
}

std::ostream &operator<<(std::ostream &os, const TInputData &data) {
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