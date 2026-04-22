#pragma once

#include <vector>

#include "path.hpp"
#include "../utils/problem_arguments.hpp"
#include "../include/operator_selector.hpp"

struct OptimizationContext {
    size_t inner_iterations_without_improve = 50;
    size_t inter_iterations_without_improve = 200;
    size_t max_or_opt_size = 10;
    size_t unvisited_candidates = 10;
    bool take_first_improve = false;
    /// Не вызывать внутренние операции, которые добавляют/удаляют/меняют набор клиентов в туре.
    bool inner_preserve_vertex_set = false;
};

bool DoInnerOptimization(
    TPath& path,
    const TInputData& inputData,
    const OptimizationContext& context,
    TOperatorSelector& selector
);


bool DoInterOptimization(
    TPath& path1,
    TPath& path2,
    const TInputData& inputData,
    TOperatorSelector& selector,
    std::mt19937& rng
);

void Optimize(std::vector<TPath>& paths, const TInputData& inputData, const OptimizationContext& context);
