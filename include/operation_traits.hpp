#pragma once

#include "adaptive_weights.hpp"
#include "inner_operation.hpp"
#include "inter_operation.hpp"

#include <array>
#include <string_view>

template <>
struct TOperationTraits<TInnerOperations::EInnerOperation> {
    using TEnum = TInnerOperations::EInnerOperation;

    static constexpr std::array<std::string_view, static_cast<size_t>(TEnum::Last)> kNames = {
        "SwapAdjacent",
        "SwapAny",
        "Shift",
        "TwoOpt",
        "OrOpt",
        "PickUnvisited",
        "Drop",
        "Replace",
        "DoubleBridge",
    };

    static std::string_view Name(TEnum op) {
        return kNames[static_cast<size_t>(op)];
    }
};

template <>
struct TOperationTraits<TInterOperations::EInterOperation> {
    using TEnum = TInterOperations::EInterOperation;

    static constexpr std::array<std::string_view, static_cast<size_t>(TEnum::Last)> kNames = {
        "Relocate",
        "Swap",
        "TwoOpt",
        "Cross",
        "RelocateSegment",
        "Glue",
    };

    static std::string_view Name(TEnum op) {
        return kNames[static_cast<size_t>(op)];
    }
};
