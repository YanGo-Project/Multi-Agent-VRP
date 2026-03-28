#pragma once

#include <vector>

#include "path.hpp"
#include "../utils/problem_arguments.hpp"

struct OptimizationContext {
    size_t inner_iterations_without_improve = 50;
    size_t inter_iterations_without_improve = 200;
    size_t max_or_opt_size = 10;
    size_t unvisited_candidates = 10;
};

bool DoInnerOptimization(TPath& path, const TInputData& inputData, const OptimizationContext& context);

bool DoInterOptimization(TPath& path1, TPath& path2, const TInputData& inputData);

void Optimize(std::vector<TPath>& paths, const TInputData& inputData, const OptimizationContext& context);
