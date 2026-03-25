#pragma once

#include <vector>

#include "path.hpp"
#include "../utils/problem_arguments.hpp"

class TInterOperations {
public:
    enum class EInterOperation : uint8_t {
        Relocate = 0,
        Swap     = 1,
        TwoOpt   = 2,
        Cross    = 3,
    };

    static constexpr int kInterOperationsCount = 4;

    struct RejectStats {
        int vertex_limit = 0;
        int time_exceed  = 0;
        int dist_exceed  = 0;
        int no_gain      = 0;
    };

    bool DoOperation(TPath& path1, TPath& path2, const TInputData& inputData,
                     EInterOperation operation);

private:
    using TOperationFn = bool (TInterOperations::*)(TPath&, TPath&, const TInputData&, RejectStats&);

    bool Relocate(TPath& path1, TPath& path2, const TInputData& inputData, RejectStats& stats);
    bool Swap    (TPath& path1, TPath& path2, const TInputData& inputData, RejectStats& stats);
    bool TwoOpt  (TPath& path1, TPath& path2, const TInputData& inputData, RejectStats& stats);
    bool Cross   (TPath& path1, TPath& path2, const TInputData& inputData, RejectStats& stats);
};
