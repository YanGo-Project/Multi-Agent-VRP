#pragma once

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
        PickUnvisited   = 5,
        Drop            = 6,
        Replace         = 7,  // Gunawan et al. (2015) «ILS for TOPTW»
        DoubleBridge    = 8,  // Ropke & Pisinger (2006)
        Last            = 9,
    };

    static constexpr uint8_t kInnerOperationsCount = static_cast<uint8_t>(EInnerOperation::Last);

    struct TInnerOperationContext {
        size_t orOptSize;
        size_t unvisiedCandidatesCount;
        bool takeFirstImprove = false;
    };

    bool DoOperation(TPath& path, const TInputData& inputData, TInnerOperationContext& context, EInnerOperation operation);

private:
    using TInnerOperationFn = bool (TInnerOperations::*)(TPath&, const TInputData&, TInnerOperationContext& context);

    bool Shift(TPath& path, const TInputData& inputData, TInnerOperationContext& context);
    bool SwapAdjacent(TPath& path, const TInputData& inputData, TInnerOperationContext& context);
    bool SwapAny(TPath& path, const TInputData& inputData, TInnerOperationContext& context);
    bool TwoOpt(TPath& path, const TInputData& inputData, TInnerOperationContext& context);
    bool OrOpt(TPath& path, const TInputData& inputData, TInnerOperationContext& context);
    bool PickUnvisited(TPath& path, const TInputData& inputData, TInnerOperationContext& context);
    bool Drop(TPath& path, const TInputData& inputData, TInnerOperationContext& context);
    bool Replace(TPath& path, const TInputData& inputData, TInnerOperationContext& context);
    bool DoubleBridge(TPath& path, const TInputData& inputData, TInnerOperationContext& context);
};