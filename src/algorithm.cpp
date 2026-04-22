#include "../include/algorithm.hpp"
#include "../include/inner_operation.hpp"
#include "../include/inter_operation.hpp"

#include <algorithm>
#include <random>
#include <thread>
#include <vector>
#include <mutex>
#include <iostream>

namespace {
std::mutex unvisited_mutex;
}

constexpr uint64_t kNeedUseMutex = 
    (uint64_t{1} << static_cast<uint8_t>(TInnerOperations::EInnerOperation::PickUnvisited)) |
    (uint64_t{1} << static_cast<uint8_t>(TInnerOperations::EInnerOperation::Drop)) |
    (uint64_t{1} << static_cast<uint8_t>(TInnerOperations::EInnerOperation::Replace));


bool DoInnerOptimization(
    TPath& path,
    const TInputData& inputData,
    const OptimizationContext& context,
    TOperatorSelector& selector
) {
    size_t no_improve = 0;
    bool any_improved = false;
    
    std::mt19937 rng{std::random_device{}()};

    TInnerOperations inner_ops;
    const size_t unvisited_candidates = std::max(context.unvisited_candidates, 1ul);

    while (no_improve < context.inner_iterations_without_improve) {

        const size_t or_opt_size = std::min(no_improve + 2, context.max_or_opt_size);
        TInnerOperations::TInnerOperationContext inner_operation_context{
            .orOptSize = or_opt_size,
            .unvisiedCandidatesCount = unvisited_candidates,
            .takeFirstImprove = context.take_first_improve,
        };

        TInnerOperations::EInnerOperation inner_operation = selector.SelectInnerOp(path.agent_idx, rng);

        bool improved = false;
        const bool need_mutex = (kNeedUseMutex >> static_cast<uint8_t>(inner_operation)) & 1;

        if(need_mutex && context.inner_preserve_vertex_set) {
            continue;
        }
 
        if (need_mutex) {
            if (unvisited_mutex.try_lock()) {
                improved = inner_ops.DoOperation(path, inputData, inner_operation_context, inner_operation);
                unvisited_mutex.unlock();
            } else {
                continue;
            }
        } else {
            improved = inner_ops.DoOperation(path, inputData, inner_operation_context, inner_operation);
        }

        EOutcome outcome = improved ? EOutcome::Improved : EOutcome::NotImproved;
        selector.UpdateInnerOp(path.agent_idx, inner_operation, outcome);

        if (improved) {
            no_improve = 0;
            any_improved = true;
        } else {
            ++no_improve;
        }
    }

    return any_improved;
}


bool DoInterOptimization(
    TPath& path1,
    TPath& path2,
    const TInputData& inputData,
    TOperatorSelector& selector,
    std::mt19937& rng
) {
    TInterOperations inter_ops;

    TInterOperations::EInterOperation op = selector.SelectInterOp(rng);
    bool improved = inter_ops.DoOperation(path1, path2, inputData, op);

    EOutcome outcome = improved ? EOutcome::Improved : EOutcome::NotImproved;
    selector.UpdateInterOp(op, outcome);

    return improved;
}


void Optimize(
    std::vector<TPath>& paths,
    const TInputData& inputData,
    const OptimizationContext& context
) {
    size_t no_improve = 0;

    std::mt19937 rng{std::random_device{}()};
    std::uniform_int_distribution<size_t> path_dist(0, paths.size() - 1);

    TOperatorSelector selector;
    TOperatorSelectorConfig selectorConfig;

    selector.Init(paths.size(), selectorConfig);

    std::vector<uint8_t> inner_improved(paths.size(), 0);

    while (no_improve < context.inter_iterations_without_improve) {

        {
            std::vector<std::thread> threads;
            threads.reserve(paths.size());

            for (size_t i = 0; i < paths.size(); ++i) {
                threads.emplace_back(
                    [&paths, &inputData, &context, &inner_improved, &selector, i]
                {
                    inner_improved[i] = DoInnerOptimization(paths[i], inputData, context, selector) ? 1u : 0u;
                });
            }

            for (auto& t : threads) {
                t.join();
            }
        }

        bool inter_ok = false;
        if (paths.size() > 1) {
            size_t p1 = path_dist(rng);
            size_t p2 = path_dist(rng);
            while (p1 == p2) {
                p2 = path_dist(rng);
            }

            inter_ok = DoInterOptimization(paths[p1], paths[p2], inputData,selector, rng);
        }

        const bool any_inner_ok = std::any_of(
                inner_improved.begin(), inner_improved.end(),
                [](uint8_t v) { return v != 0; }
            );

        if (any_inner_ok) {
            selector.UpdateLevel(ELevel::Inner, EOutcome::Improved);
        } else {
            selector.UpdateLevel(ELevel::Inner, EOutcome::NotImproved);
        }

        if (inter_ok) {
            selector.UpdateLevel(ELevel::Inter, EOutcome::Improved);
        } else {
            selector.UpdateLevel(ELevel::Inter, EOutcome::NotImproved);
        }

        if (inter_ok || any_inner_ok) {
            no_improve = 0;
        } else {
            ++no_improve;
        }
    }

    selector.PrintStats();
}
