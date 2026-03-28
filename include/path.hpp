#pragma once

#include <ostream>

#include "first_step.hpp"

using TRoute = std::vector<FirstStepAnswer::points_type>;

struct TPath {
    using score_type = FirstStepAnswer::score_type;

    TRoute tour;
    int64_t distance{0};
    int64_t time{0};
    int64_t score{0};

    int64_t max_distance{0};
    int64_t max_time{0};
    FirstStepAnswer::points_type max_vertexes{0};
    FirstStepAnswer::points_type min_vertexes{0};
    FirstStepAnswer::points_type depo{0};
    uint32_t agent_idx{0};


    bool operator==(const TPath &other) const {
        if (tour.size() != other.tour.size()) {
            return false;
        }
        if (time != other.time) {
            return false;
        }
        if (distance != other.distance) {
            return false;
        }
        if (score != other.score) {
            return false;
        }
        for (size_t i = 0; i < tour.size(); ++i) {
            if (tour[i] != other.tour[i]) {
                return false;
            }
        }
        return true;
    }

    bool operator<(const TPath& other) const {
        return score < other.score;
    }

    std::string get_data_to_csv() const {
        return std::to_string(score) + "," + std::to_string(time) + "," + std::to_string(distance);
    }

};

std::ostream& operator<<(std::ostream& os, const TPath& path);