#include "utils/json_parser.hpp"

#ifdef DEBUG
#include "utils/debug.h"
#endif

#include "include/first_step.hpp"

#include <iostream>
#include <fstream>
#include <thread>
#include <vector>
#include <algorithm>
#include <optional>

using Solution = std::vector<FirstStepAnswer>;

Solution Solve(InputData &&input, const ProgramArguments& args) {

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
            result = DoFirstStep<std::numeric_limits<InputData::points_type>::max(), true>(input);
        }
        
        if (result.empty()) {
            std::cout << "No solution for agent #" << i << std::endl;
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

    InputData input;
    if (!JsonParser::ParseInputDataFromJson(args.problemJsonPath, input)) {
        return -2;
    }

    std::cout << input;

    auto solutions = Solve(std::move(input), args);
    for (size_t i = 0; i < input.agents_count; ++i) {
        std::cout << "Path for agent: #" << i << "\t" << solutions[i] << "\n";
    }

    return 0;
}