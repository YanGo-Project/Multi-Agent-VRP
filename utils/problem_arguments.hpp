#pragma once

#include <cstdint>
#include <vector>
#include <string>
#include <map>
#include <unordered_set>

struct MetaParameters {
    int population_size;
    int alpha;
    double beta;
    int nloop;
    int kMax;
    double p;
    int max_iter_without_solution;
    size_t max_crossover_candidates;
};


struct ProgramArguments {
    std::string problemJsonPath;
    std::string solutionJsonPath;
    uint64_t time;
    std::string csv_file;
    bool save_csv;
    MetaParameters meta;
};

bool ParseProgramArguments(int argc, char *argv[], ProgramArguments &args);

struct InputData {
    using points_type = uint16_t;
    /// количество точек в задаче, включая склад.
    points_type points_count{};
    /// количество агентов в задаче
    points_type agents_count{};
    /// время старта агента относительно запуска программы
    std::vector<int64_t> agent_start_time;
    /// минимальная загрузка исполнителя для каждого агента
    std::vector<points_type> min_load{};
    /// максимальная загрузка исполнителя для каждого агента
    std::vector<points_type> max_load{};
    /// максимальное время в построенной миссии для каждого агента
    std::vector<int64_t> max_time{};
    /// максимальное расстояние в построенной миссии для каждого агента
    std::vector<int64_t> max_distance{};
    /// матрица расстояний между точками. Размерность матрицы
    std::vector<std::vector<int64_t>> distance_matrix;
    /// Матрица времени перемещения между точками.
    /// Размерность матрицы @time_steps x @points_count x @points_count,
    /// склад/стартовая точка исполнителя в матрице имеет индекс 0.
    std::vector<std::vector<std::vector<int64_t>>> time_matrix;
    /// массив "важностей" всех точек, кроме склада.
    /// Размерность массива @points_count - 1.
    std::vector<int64_t> point_scores;
    /// массив времён на обслуживание каждой точки, кроме склада.
    /// Размерность массива @points_count - 1.
    std::vector<int64_t> point_service_times;

    /// 30 минут в секундах для TD цены перехода
    static constexpr int64_t time_duration = 30 * 60;

    [[nodiscard]] int64_t get_time_dependent_cost(int64_t time, points_type from, points_type to) const;

    [[nodiscard]] std::tuple<int64_t, int64_t, int64_t> get_path_time_distance_score(const std::vector<points_type> &path) const;

    std::map<points_type, points_type> from_new_to_old{};

    /// meta информация для многоагентного варианта
    std::unordered_set<points_type> visited_points{};
    points_type current_agent{};
    bool is_mapped = false;
};

std::ostream &operator<<(std::ostream &os, const InputData &data);

struct OutData {
    using points_type = InputData::points_type;
    /// последовательность индексов точек, составляющих найденный маршрут.
    std::vector<points_type> route;
    /// количество точек в решении.
    points_type solution_size{};
    /// ETA на прохождение маршрута (по @time_matrix и @point_service_times).
    int64_t total_time{};
    ///  суммарное расстояние в маршруте (по @distance_matrix).
    int64_t total_distance{};
    /// суммарный скор найденного маршрута (по @point_scores и @time_matrix).
    int64_t total_value{};
};

std::ostream &operator<<(std::ostream &os, const OutData &solution);