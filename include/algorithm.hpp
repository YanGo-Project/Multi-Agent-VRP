#pragma once

#include <chrono>
#include <optional>
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
    // не вызывать внутренние операции, которые добавляют/удаляют/меняют набор клиентов в туре
    bool inner_preserve_vertex_set = false;
    size_t glue_max_inner_iterations = 200;
    // количество случайных пар маршрутов прогнать через Glue до основного цикла
    size_t glue_warmup_attempts = 48;
    // лимит работы в секундах
    uint64_t time_limit_seconds = 0;
};

bool DoInnerOptimization(
    TPath& path,
    const TInputData& inputData,
    const OptimizationContext& context,
    TOperatorSelector& selector,
    std::optional<std::chrono::steady_clock::time_point> deadline = std::nullopt
);


bool DoInterOptimization(
    TPath& path1,
    TPath& path2,
    const TInputData& inputData,
    TOperatorSelector& selector,
    const OptimizationContext& context,
    std::mt19937& rng
);

void Optimize(std::vector<TPath>& paths, const TInputData& inputData, const OptimizationContext& context);
