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
        Last            = 5,
    };

    static constexpr int kInterOperationsCount = 5;

    bool DoOperation(TPath& path1, TPath& path2, const TInputData& inputData,
                     EInterOperation operation);

private:
    using TOperationFn = bool (TInterOperations::*)(TPath&, TPath&, const TInputData&);

    bool Relocate(TPath& path1, TPath& path2, const TInputData& inputData);
    bool Swap(TPath& path1, TPath& path2, const TInputData& inputData);
    bool TwoOpt(TPath& path1, TPath& path2, const TInputData& inputData);
    bool Cross(TPath& path1, TPath& path2, const TInputData& inputData);
    bool RelocateSegment(TPath& path1, TPath& path2, const TInputData& inputData);
};
