#include "utils/json_parser.hpp"

#ifdef DEBUG
#include "utils/debug.h"
#endif

#include "include/first_step.hpp"
#include "include/algorithm.hpp"

#include <iostream>
#include <fstream>
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
                .score        = 0,
                .max_distance = input.max_distance[agent],
                .max_time     = input.max_time[agent],
                .max_vertexes = input.max_load[agent],
                .min_vertexes = input.min_load[agent],
                .start_depo   = input.agent_depots[agent],
                .end_depo     = input.agent_depots_end[agent],
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
            .start_depo   = input.agent_depots[agent],
            .end_depo     = input.agent_depots_end[agent],
            .agent_idx    = agent,
        });
    }

    return paths;
}

TPath ChooseBestCandidatePath(std::vector<FirstStepAnswer>&& candidates, TInputData& input, const OptimizationContext& ctx, uint32_t agent) {
    
    auto paths = ConstructPathsFromCandidates(std::move(candidates), input, agent);
    (void)ctx;

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

        auto result = DoFirstStep<true>(input, i);

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

    const size_t max_inter = static_cast<size_t>(std::max(1, args.meta.max_iter_without_solution));
    const size_t inner_stagn = std::clamp(max_inter, size_t{32}, size_t{240});

    OptimizationContext opt_ctx{
        .inner_iterations_without_improve = inner_stagn,
        .inter_iterations_without_improve = max_inter,
        .max_or_opt_size                  = 10,
        .unvisited_candidates             = 10,
        .take_first_improve               = false,
        .time_limit_seconds               = args.time,
    };

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
    JsonParser::WriteAgentsJson(paths, JsonParser::MakeJsonPath(args.problemJsonPath, "before"));

    Optimize(paths, input, opt_ctx);
    print_paths("After local search");
    JsonParser::WriteAgentsJson(paths, JsonParser::MakeJsonPath(args.problemJsonPath, "after"));

    return 0;
}