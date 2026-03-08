#pragma once

#include <cstdint>
#include <vector>
#include <ostream>
#include <unordered_set>
#include <set>
#include <limits>

#include "../utils/problem_arguments.hpp"

struct FirstStepAnswer {

    using score_type = int64_t;
    using points_type = InputData::points_type;
    static constexpr score_type default_value = std::numeric_limits<score_type>::min() + 1;

    /// значение целевой функции
    score_type value = default_value;
    score_type distance = 0;
    score_type time = 0;
    /// список вершин в порядке обхода в пути
    std::vector<points_type> vertexes{0};

    std::string get_data_to_csv() const {
        return std::to_string(value) + "," + std::to_string(time) + "," + std::to_string(distance);
    }

    bool operator<(const FirstStepAnswer& other) const {
        return value < other.value;
    }

    bool operator==(const FirstStepAnswer& other) const {
        return std::set<points_type>(vertexes.begin(), vertexes.end()) == 
               std::set<points_type>(other.vertexes.begin(), other.vertexes.end());
    }
};

template<size_t bitset_size = std::numeric_limits<InputData::points_type>::max(), bool is_time_dependent = false>
std::vector<FirstStepAnswer> DoFirstStep(const InputData &input);

std::ostream &operator<<(std::ostream &os, const FirstStepAnswer &answer);

