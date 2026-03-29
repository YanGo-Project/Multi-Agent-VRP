#pragma once

#include "problem_arguments.hpp"
#include <nlohmann/json.hpp>
#include <string>
#include <vector>

struct TPath;

namespace JsonParser {
    
    std::string MakeJsonPath(const std::string& base, const std::string& suffix);

    bool ParseInputDataFromJson(const std::string &jsonPath, TInputData &arg);

    bool ParseSolutionFromJson(const std::string &jsonPath, OutData& solution);

    bool WriteSolutionToJsonFile(const std::string &jsonPath, OutData &&solution);

    bool WriteAgentsJson(const std::vector<TPath>& paths, const std::string& filepath);
}