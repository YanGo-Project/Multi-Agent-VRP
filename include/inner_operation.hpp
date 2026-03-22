#pragma once

#include <functional>
#include <random>
#include <vector>

#include "path.hpp"
#include "../utils/problem_arguments.hpp"

class TInnerOperations {
public:
    enum class EInnerOperation : uint8_t {
        SwapAdjacent    = 0,
        SwapAny         = 1,
        Shift           = 2,
        TwoOpt          = 3,
        OrOpt           = 4,
    };

    static constexpr uint8_t kInnerOperationsCount = 5;

    struct TInnerOperationContext {
        size_t orOptSize;
    };

    bool DoOperation(TPath& path, const TInputData& inputData, TInnerOperationContext& context, EInnerOperation operation);

private:
    using TInnerOperationFn = bool (TInnerOperations::*)(TPath&, const TInputData&, TInnerOperationContext& context);

    bool Shift(TPath& path, const TInputData& inputData, TInnerOperationContext& context);
    bool SwapAdjacent(TPath& path, const TInputData& inputData, TInnerOperationContext& context);
    bool SwapAny(TPath& path, const TInputData& inputData, TInnerOperationContext& context);
    bool TwoOpt(TPath& path, const TInputData& inputData, TInnerOperationContext& context);
    bool OrOpt(TPath& path, const TInputData& inputData, TInnerOperationContext& context);
};