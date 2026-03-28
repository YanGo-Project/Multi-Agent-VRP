#include "utils/json_parser.hpp"

#ifdef DEBUG
#include "utils/debug.h"
#endif

#include "include/first_step.hpp"
#include "include/algorithm.hpp"

#include <iostream>
#include <fstream>
#include <thread>
#include <vector>
#include <algorithm>
#include <optional>

using Solution = std::vector<FirstStepAnswer>;

std::vector<TPath> ConstructPathsFromCandidates(std::vector<FirstStepAnswer>&& firstStep, TInputData& input, const uint32_t agent){

    if (firstStep.empty()) { [[unlikely]]
        return {
            TPath{
                .distance     = 0,
                .time         = 0,
                .score        = std::numeric_limits<TPath::score_type>::min() + 1,
                .max_distance = input.max_distance[agent],
                .max_time     = input.max_time[agent],
                .max_vertexes = input.max_load[agent],
                .min_vertexes = input.min_load[agent],
                .depo         = input.agent_depots[agent],
                .agent_idx    = agent,
            }
        };
    }

    std::vector<TPath> paths;
    paths.reserve(firstStep.size());

    for (auto&& candidate : firstStep) {
        paths.push_back(TPath{
            .tour         = std::move(candidate.vertexes),
            .distance     = candidate.distance,
            .time         = candidate.time,
            .score        = candidate.value,
            .max_distance = input.max_distance[agent],
            .max_time     = input.max_time[agent],
            .max_vertexes = input.max_load[agent],
            .min_vertexes = input.min_load[agent],
            .depo         = input.agent_depots[agent],
            .agent_idx    = agent,
        });
    }

    return paths;
}

TPath ChooseBestCandidatePath(std::vector<FirstStepAnswer>&& candidates, TInputData& input, const OptimizationContext& ctx, uint32_t agent) {
    
    auto paths = ConstructPathsFromCandidates(std::move(candidates), input, agent);

    std::vector<std::thread> threads;
    threads.reserve(paths.size());
    for (size_t i = 0; i < paths.size(); ++i) {
        threads.emplace_back([&paths, &input, &ctx, i] {
           DoInnerOptimization(paths[i], input, ctx);
        });
    }

    for (auto& t : threads) {
        t.join();
    }

    size_t bestPathIdx = 0;
    for (size_t i = 1; i < paths.size(); ++i) {
        if (paths[bestPathIdx] < paths[i]) {
            bestPathIdx = i;
        }
    }

    return paths[bestPathIdx];
}

std::vector<TPath> FisrtStep(TInputData& input, const ProgramArguments& args, const OptimizationContext& ctx) {

    std::vector<TPath> pathsFromFirstStep;
    pathsFromFirstStep.reserve(input.agents_count);

    for (uint32_t i = 0; i < input.agents_count; ++i) {

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

        auto bestPath = ChooseBestCandidatePath(std::move(result), input, ctx, i);

        for (auto visited : bestPath.tour) {
            input.visited_points.insert(visited);
        }

        pathsFromFirstStep.emplace_back(std::move(bestPath));
    }

    return pathsFromFirstStep;
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

    OptimizationContext opt_ctx{
        .inner_iterations_without_improve = 200,
        .inter_iterations_without_improve = static_cast<size_t>(args.meta.max_iter_without_solution),
        .max_or_opt_size                  = 10,
        .unvisited_candidates             = 10,
    };

    std::cout << "Agents: " << input.agents_count << "\n";

    auto paths = FisrtStep(input, args, opt_ctx);
    ConstructUnvisitedVertexes(input);


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
    Optimize(paths, input, opt_ctx);
    print_paths("After local search");

    return 0;
}