#include "problem_arguments_impl.hpp"
#include <unistd.h>
#include <iostream>

#ifdef DEBUG
#include "debug.h"
#endif

bool ParseProgramArguments(int argc, char *argv[], ProgramArguments &args) {
    int opt;
    args.save_csv = false;
    args.time = 0;
    
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
    return EvalVirtualTour(path, path.tour.size(),
        [&](size_t i) -> points_type { return path.tour[i]; });
}

bool TInputData::check_path_values(const TPath& path) const {
    auto [distance, time, score] = get_path_distance_time_score(path);
    if (distance != path.distance || time != path.time || score != path.score) {
        std::cout << "We have some bad news for path: " << path << "\n"
        << "saved path metrics: \n"
        << distance << " " << path.distance << " " 
        << time << " " << path.time << " " 
        << score << " " << path.score << std::endl;
        return false;
    }
    return true;
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