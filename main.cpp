#include "utils/json_parser.hpp"

#ifdef DEBUG
#include "utils/debug.h"
#endif

#include "include/first_step.hpp"
#include "include/inter_operation.hpp"

#include <iostream>
#include <fstream>
#include <thread>
#include <vector>
#include <algorithm>
#include <optional>

using Solution = std::vector<FirstStepAnswer>;


Solution Solve(TInputData& input, const ProgramArguments& args) {

    std::vector<FirstStepAnswer> firstStepAnswers;
    firstStepAnswers.resize(input.agents_count);

    for (size_t i = 0; i < input.agents_count; ++i) {
        input.current_agent = i;

        std::vector<FirstStepAnswer> result;
        if (input.points_count < 128) {
            result = DoFirstStep<128, true>(input);
        } else if (input.points_count < 256) {
            result = DoFirstStep<256, true>(input);
        } else if (input.points_count < 512) {
            result = DoFirstStep<512, true>(input);
        } else {
            result = DoFirstStep<std::numeric_limits<TInputData::points_type>::max(), true>(input);
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

int main(int argc, char *argv[]) {
    ProgramArguments args;
    if (!ParseProgramArguments(argc, argv, args)) {
        return -1;
    }

    TInputData input;
    if (!JsonParser::ParseInputDataFromJson(args.problemJsonPath, input)) {
        return -2;
    }

    std::cout << input;

    auto firstStepAnswers = Solve(input, args);

    // строим TPath из результатов первого шага
    // vertexes имеет вид [0 (депо), v1, v2, ..., vn, 0 (депо)] — обрезаем оба конца
    std::vector<TPath> paths;
    paths.reserve(firstStepAnswers.size());

    for (uint32_t i = 0; i < firstStepAnswers.size(); ++i) {
        auto& ans = firstStepAnswers[i];

        TRoute route = std::move(ans.vertexes);
        if (route.size() >= 2) {
            route.erase(route.begin());  // убираем стартовый депо
            route.pop_back();            // убираем финальный депо
        } else {
            route.clear();
        }

        paths.push_back(TPath{
            .tour         = std::move(route),
            .distance     = ans.distance,
            .time         = ans.time,
            .score        = ans.value,
            .max_distance = input.max_distance[i],
            .max_time     = input.max_time[i],
            .max_vertexes = input.max_load[i],
            .min_vertexes = input.min_load[i],
            .depo         = 0,
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

    TInterOperations ops;

    ops.RunLocalSearch(paths, input, args.meta.max_iter_without_solution);
    print_paths("After local search");

    return 0;
}