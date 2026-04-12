#pragma once

#include "operation_traits.hpp"

#include <vector>

enum class ELevel : uint8_t {
    Inner = 0,
    Inter = 1,
    Last  = 2,
};

template <>
struct TOperationTraits<ELevel> {
    static constexpr std::array<std::string_view, static_cast<size_t>(ELevel::Last)> kNames = {
        "Inner",
        "Inter",
    };
    static std::string_view Name(ELevel op) {
        return kNames[static_cast<size_t>(op)];
    }
};

struct TOperatorSelectorConfig {
    TWeightsConfig innerConfig = { .decay = 0.8, .initialWeight = 10.0, .improvedWeight = 100.0, .notImprovedWeight = 5.0 };
    TWeightsConfig interConfig = { .decay = 0.8, .initialWeight = 10.0, .improvedWeight = 100.0, .notImprovedWeight = 5.0 };
    TWeightsConfig levelConfig = { .decay = 0.9, .initialWeight = 10.0, .improvedWeight = 100.0, .notImprovedWeight = 5.0 };
};


class TOperatorSelector {
public:
    using EInnerOp = TInnerOperations::EInnerOperation;
    using EInterOp = TInterOperations::EInterOperation;

    void Init(size_t numPaths, const TOperatorSelectorConfig& config) {
        config_ = config;

        intraWeightsPerPath_.clear();
        intraWeightsPerPath_.reserve(numPaths);
        for (size_t i = 0; i < numPaths; ++i) {
            intraWeightsPerPath_.emplace_back(config.innerConfig);
        }

        interWeights_ = TAdaptiveWeights<EInterOp>(config.interConfig);
        levelWeights_ = TAdaptiveWeights<ELevel>(config.levelConfig);
    }

    void Init(size_t numPaths) {
        Init(numPaths, TOperatorSelectorConfig{});
    }

    ELevel SelectLevel(std::mt19937& rng) {
        return levelWeights_.Select(rng);
    }

    void UpdateLevel(ELevel level, EOutcome outcome) {
        levelWeights_.Update(level, outcome);
    }

    EInnerOp SelectInnerOp(size_t pathIndex, std::mt19937& rng) {
        assert(pathIndex < intraWeightsPerPath_.size());
        return intraWeightsPerPath_[pathIndex].Select(rng);
    }

    void UpdateInnerOp(size_t pathIndex, EInnerOp op, EOutcome outcome) {
        assert(pathIndex < intraWeightsPerPath_.size());
        intraWeightsPerPath_[pathIndex].Update(op, outcome);
    }

    EInterOp SelectInterOp(std::mt19937& rng) {
        return interWeights_.Select(rng);
    }

    void UpdateInterOp(EInterOp op, EOutcome outcome) {
        interWeights_.Update(op, outcome);
    }

    void PrintStats() const {
        std::cout << "=== Level weights ===\n";
        levelWeights_.Print();

        std::cout << "\n=== Inter-route weights ===\n";
        interWeights_.Print();

        std::cout << "\n=== Intra-route weights (per path) ===\n";
        for (size_t r = 0; r < intraWeightsPerPath_.size(); ++r) {
            std::cout << "--- Path " << r << " ---\n";
            intraWeightsPerPath_[r].Print();
        }
    }

    const TAdaptiveWeights<EInnerOp>& GetIntraWeights(size_t pathIndex) const {
        return intraWeightsPerPath_[pathIndex];
    }
    const TAdaptiveWeights<EInterOp>& GetInterWeights() const { return interWeights_; }
    const TAdaptiveWeights<ELevel>&   GetLevelWeights() const { return levelWeights_; }

private:
    TOperatorSelectorConfig config_;
    std::vector<TAdaptiveWeights<EInnerOp>> intraWeightsPerPath_;
    TAdaptiveWeights<EInterOp> interWeights_;
    TAdaptiveWeights<ELevel>   levelWeights_;
};


