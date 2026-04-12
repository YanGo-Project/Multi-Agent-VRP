#pragma once

#include <array>
#include <cassert>
#include <cstdint>
#include <iostream>
#include <iomanip>
#include <numeric>
#include <random>
#include <string_view>

enum class EOutcome : uint8_t {
    Improved    = 0,
    NotImproved = 1,
};

struct TWeightsConfig {
    double decay         = 0.8;
    double initialWeight = 10.0;
    double improvedWeight = 100.0;
    double notImprovedWeight = 5.0;
};

template <typename TEnum>
struct TOperationTraits;

template <typename TEnum>
class TAdaptiveWeights {
public:
    static constexpr size_t kCount = static_cast<size_t>(TEnum::Last);

    TAdaptiveWeights() {
        Reset();
    }

    explicit TAdaptiveWeights(const TWeightsConfig& config) : config_(config)
    {
        Reset();
    }

    TEnum Select(std::mt19937& rng) const {
        const double total = Sum();
        std::uniform_real_distribution<double> dist(0.0, total);
        double r = dist(rng);

        double cumulative = 0.0;
        for (size_t i = 0; i < kCount; ++i) {
            cumulative += weights_[i];
            if (r <= cumulative) {
                return static_cast<TEnum>(i);
            }
        }
        return static_cast<TEnum>(kCount - 1);
    }

    void Update(TEnum op, EOutcome outcome) {
        const size_t idx = static_cast<size_t>(op);
        assert(idx < kCount);

        auto score = config_.notImprovedWeight;

        totalAttempts_[idx]++;
        if (outcome == EOutcome::Improved) {
            totalSuccesses_[idx]++;
            score = config_.improvedWeight;
        }

        weights_[idx] = (1 - config_.decay) * weights_[idx] + config_.decay * score;
    }

    double GetWeight(TEnum op) const {
        return weights_[static_cast<size_t>(op)];
    }

    double GetProbability(TEnum op) const {
        return weights_[static_cast<size_t>(op)] / Sum();
    }

    std::array<double, kCount> GetProbabilities() const {
        const double total = Sum();
        std::array<double, kCount> probs;
        for (size_t i = 0; i < kCount; ++i) {
            probs[i] = weights_[i] / total;
        }
        return probs;
    }

    int GetTotalAttempts(TEnum op) const {
        return totalAttempts_[static_cast<size_t>(op)];
    }

    int GetTotalSuccesses(TEnum op) const {
        return totalSuccesses_[static_cast<size_t>(op)];
    }

    void Print() const {
        auto probs = GetProbabilities();
        for (size_t i = 0; i < kCount; ++i) {
            const auto op = static_cast<TEnum>(i);
            const int att = totalAttempts_[i];
            const int suc = totalSuccesses_[i];
            const double globalRate = (att > 0)
                ? (100.0 * suc / att) : 0.0;

            std::cout << "  " << std::left << std::setw(20)
                      << TOperationTraits<TEnum>::Name(op)
                      << " w=" << std::fixed << std::setprecision(4) << weights_[i]
                      << "  p=" << std::setprecision(1) << (probs[i] * 100.0) << "%"
                      << "  n=" << att
                      << "  ok=" << suc
                      << "  rate=" << std::setprecision(3) << globalRate << "%"
                      << "\n";
        }
    }

private:
    void Reset() {
        weights_.fill(config_.initialWeight);
        totalAttempts_.fill(0);
        totalSuccesses_.fill(0);
    }

    double Sum() const {
        return std::accumulate(weights_.begin(), weights_.end(), 0.0);
    }

    TWeightsConfig config_;

    std::array<double, kCount> weights_;

    std::array<int, kCount> totalAttempts_;
    std::array<int, kCount> totalSuccesses_;
};

