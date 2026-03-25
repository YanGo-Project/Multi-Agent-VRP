#pragma once

#include <vector>

#include "path.hpp"
#include "../utils/problem_arguments.hpp"

struct OptimizationContext {
    size_t inner_iterations_without_improve = 50;
    size_t inter_iterations_without_improve = 200;
    size_t max_or_opt_size = 10;
};

void Optimize(std::vector<TPath>& paths, const TInputData& inputData, const OptimizationContext& context);
