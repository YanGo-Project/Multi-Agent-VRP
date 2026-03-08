#pragma once

#include "problem_arguments.hpp"
#include <nlohmann/json.hpp>

namespace JsonParser {
    bool ParseInputDataFromJson(const std::string &jsonPath, InputData &arg);

    bool ParseSolutionFromJson(const std::string &jsonPath, OutData& solution);

    bool WriteSolutionToJsonFile(const std::string &jsonPath, OutData &&solution);

    // bool WriteSolutionTojsonFile(const std::string& jsonPath, Solution && solution);
}