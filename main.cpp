#include "utils/json_parser.hpp"

#ifdef DEBUG
#include "utils/debug.h"
#endif

#include "include/first_step.hpp"
#include "include/inter_operation.hpp"
#include "include/algorithm.hpp"

#include <iostream>
#include <fstream>
#include <thread>
#include <vector>
#include <algorithm>
#include <optional>

using Solution = std::vector<FirstStepAnswer>;


Solution FisrtStep(TInputData& input, const ProgramArguments& args) {

    std::vector<FirstStepAnswer> firstStepAnswers;
    firstStepAnswers.resize(input.agents_count);

    for (size_t i = 0; i < input.agents_count; ++i) {

        std::vector<FirstStepAnswer> result;
        if (input.points_count < 128) {
            result = DoFirstStep<128, true>(input, i);
        } else if (input.points_count < 256) {
            result = DoFirstStep<256, true>(input, i);
        } else if (input.points_count < 512) {
            result = DoFirstStep<512, true>(input, i);
        } else {
            result = DoFirstStep<std::numeric_limits<TInputData::points_type>::max(), true>(input, i);
        }

        if (result.empty()) {
            std::cout << "No solution for agent #" << i << "\n";
            firstStepAnswers[i] = {};
            continue;
        }

        firstStepAnswers[i] = result[0];

        for (auto visited : firstStepAnswers[i].vertexes) {
            input.visited_points.insert(visited);
        }
    }

    return firstStepAnswers;
}

void ConstructUnvisitedVertexes(TInputData& input) {
    input.unvisited_points.reserve(input.points_count - input.visited_points.size());
    for (TInputData::points_type i = 0; i < input.points_count; ++i) {
        if (input.visited_points.find(i) == input.visited_points.end() &&
            input.depots_set.find(i) == input.depots_set.end()) { 
            input.unvisited_points.push_back(i);
        }
    }
}

int main(int argc, char *argv[]) {
    ProgramArguments args;
    if (!ParseProgramArguments(argc, argv, args)) {
        return -1;
    }

    TInputData input;
    if (!JsonParser::ParseInputDataFromJson(args.problemJsonPath, input)) {
        return -2;
    }

    auto firstStepAnswers = FisrtStep(input, args);
    ConstructUnvisitedVertexes(input);

    std::vector<TPath> paths;
    paths.reserve(firstStepAnswers.size());

    for (uint32_t i = 0; i < firstStepAnswers.size(); ++i) {
        auto& ans = firstStepAnswers[i];

        paths.push_back(TPath{
            .tour         = std::move(ans.vertexes),
            .distance     = ans.distance,
            .time         = ans.time,
            .score        = ans.value,
            .max_distance = input.max_distance[i],
            .max_time     = input.max_time[i],
            .max_vertexes = input.max_load[i],
            .min_vertexes = input.min_load[i],
            .depo         = input.agent_depots[i],
            .agent_idx    = i,
        });
    }

    auto print_paths = [&](const char* header) {
        std::cout << "\n=== " << header << " ===\n";
        int64_t total = 0;
        for (size_t i = 0; i < paths.size(); ++i) {
            std::cout << "Agent #" << i << "  " << paths[i];
            total += paths[i].score;
        }
        std::cout << "Total score: " << total << "\n";
    };

    print_paths("First step results");

    OptimizationContext opt_ctx{
        .inner_iterations_without_improve = 200,
        .inter_iterations_without_improve = static_cast<size_t>(args.meta.max_iter_without_solution),
        .max_or_opt_size                  = 10,
        .unvisited_candidates             = 10,
    };
    Optimize(paths, input, opt_ctx);
    print_paths("After local search");

    return 0;
}