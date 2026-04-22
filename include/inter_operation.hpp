#pragma once

#include <vector>

#include "path.hpp"
#include "../utils/problem_arguments.hpp"

class TInterOperations {
public:
    enum class EInterOperation : uint8_t {
        Relocate        = 0,
        Swap            = 1,
        TwoOpt          = 2,
        Cross           = 3,
        RelocateSegment = 4,
        Glue            = 5,
        Last            = 6,
    };

    static constexpr int kInterOperationsCount = static_cast<uint8_t>(EInterOperation::Last);

    struct TInterOperationContext {
        size_t max_glue_inner_optimization_iterations = 10;
    };

    bool DoOperation(TPath& path1, TPath& path2, const TInputData& inputData,
                     EInterOperation operation, TInterOperationContext& ctx);

private:
    using TOperationFn = bool (TInterOperations::*)(TPath&, TPath&, const TInputData&, TInterOperationContext&);

    bool Relocate(TPath& path1, TPath& path2, const TInputData& inputData, TInterOperationContext& ctx);
    bool Swap(TPath& path1, TPath& path2, const TInputData& inputData, TInterOperationContext& ctx);
    bool TwoOpt(TPath& path1, TPath& path2, const TInputData& inputData, TInterOperationContext& ctx);
    bool Cross(TPath& path1, TPath& path2, const TInputData& inputData, TInterOperationContext& ctx);
    bool RelocateSegment(TPath& path1, TPath& path2, const TInputData& inputData, TInterOperationContext& ctx);
    bool Glue(TPath& path1, TPath& path2, const TInputData& inputData, TInterOperationContext& ctx);
};
