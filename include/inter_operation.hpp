#pragma once

#include <functional>
#include <random>
#include <vector>

#include "path.hpp"
#include "../utils/problem_arguments.hpp"

class TInterOperations {
public:
    enum class EOperation {
        Relocate = 0,
        Swap     = 1,
        TwoOpt   = 2,
        Cross    = 3,
    };

    void RunLocalSearch(std::vector<TPath>& paths,
                        const TInputData&   inputData,
                        int                 max_no_improvement);

    struct RejectStats {
        int vertex_limit = 0;   ///< заблокировано ограничением min/max вершин до перебора
        int time_exceed  = 0;   ///< кандидат нарушил max_time
        int dist_exceed  = 0;   ///< кандидат нарушил max_distance
        int no_gain      = 0;   ///< кандидат допустим, но score не вырос
    };

private:
    using TOperationFn = bool (TInterOperations::*)(TPath&, TPath&, const TInputData&, RejectStats&);

    bool Relocate(TPath& path1, TPath& path2, const TInputData& inputData, RejectStats& stats);
    bool Swap    (TPath& path1, TPath& path2, const TInputData& inputData, RejectStats& stats);
    bool TwoOpt  (TPath& path1, TPath& path2, const TInputData& inputData, RejectStats& stats);
    bool Cross   (TPath& path1, TPath& path2, const TInputData& inputData, RejectStats& stats);
};