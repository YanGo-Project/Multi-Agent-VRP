#include "../include/algorithm.hpp"
#include "../include/inner_operation.hpp"
#include "../include/inter_operation.hpp"

#include <algorithm>
#include <random>
#include <thread>
#include <vector>

#include <iostream>

namespace {

bool DoInnerOptimization(TPath& path, const TInputData& inputData, const OptimizationContext& context) {
    size_t no_improve   = 0;
    bool any_improved = false;

    std::mt19937 rng{std::random_device{}()};
    std::uniform_int_distribution<uint8_t> op_dist(0, TInnerOperations::kInnerOperationsCount - 1);

    TInnerOperations inner_ops;

    while (no_improve < context.inner_iterations_without_improve) {
        const size_t or_opt_size = std::min(no_improve + 2, context.max_or_opt_size);

        TInnerOperations::TInnerOperationContext inner_operation_context{.orOptSize = or_opt_size};

        TInnerOperations::EInnerOperation inner_operation = static_cast<TInnerOperations::EInnerOperation>(op_dist(rng));
        const bool improved = inner_ops.DoOperation(path, inputData, inner_operation_context, inner_operation);

        if (improved) {
            no_improve   = 0;
            any_improved = true;
        } else {
            ++no_improve;
        }
    }

    return any_improved;
}

bool DoInterOptimization(TPath& path1, TPath& path2, const TInputData& inputData) {
    std::mt19937 rng{std::random_device{}()};
    std::uniform_int_distribution<uint8_t> op_dist(
        0, static_cast<uint8_t>(TInterOperations::kInterOperationsCount - 1));

    TInterOperations inter_ops;
    auto dst = op_dist(rng);
    const auto op = static_cast<TInterOperations::EInterOperation>(dst);
    std::cout << "InterOperation: " << (uint32_t)dst << std::endl;
    return inter_ops.DoOperation(path1, path2, inputData, op);
}

} // namespace

void Optimize(std::vector<TPath>& paths, const TInputData& inputData, const OptimizationContext& context) {

    size_t no_improve = 0;

    std::mt19937 rng{std::random_device{}()};
    std::uniform_int_distribution<size_t> path_dist(0, paths.size() - 1);

    std::vector<uint8_t> inner_improved(paths.size(), 0);

    auto print_paths = [&]() {
        std::cout << "\n=== PATHS INFO ===\n";
        int64_t total = 0;
        for (size_t i = 0; i < paths.size(); ++i) {
            std::cout << "Agent #" << i << "  " << paths[i];
            total += paths[i].score;
        }
        std::cout << "Total score: " << total << "\n";
    };

    while (no_improve < context.inter_iterations_without_improve) {

        std::cout << "Iterations withou improve: " << no_improve << "\n";
        print_paths();

        std::vector<std::thread> threads;
        threads.reserve(paths.size());

        for (size_t i = 0; i < paths.size(); ++i) {
            threads.emplace_back([&paths, &inputData, &context, &inner_improved, i] {
                inner_improved[i] = DoInnerOptimization(paths[i], inputData, context) ? 1u : 0u;
            });
        }

        for (auto& t : threads) {
            t.join();
        }

        size_t path1 = path_dist(rng);
        size_t path2 = path_dist(rng);
        while (path1 == path2) {
            path2 = path_dist(rng);
        }

        const bool inter_ok = DoInterOptimization(paths[path1], paths[path2], inputData);

        const bool any_inner_ok = std::any_of(
            inner_improved.begin(), inner_improved.end(),
            [](uint8_t v) { return v != 0; });

        if (inter_ok || any_inner_ok) {
            no_improve = 0;
            std::cout << "-------------------------------------------------------\n";
            std::cout << "Imporved: " << inter_ok << " " << any_inner_ok << " for path1 and path2: " << path1 << " " << path2 << "\n"; 
            print_paths();
            std::cout << "-------------------------------------------------------\n";
        } else {
            ++no_improve;
        }
    }
}
