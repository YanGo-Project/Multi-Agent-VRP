#include <fstream>
#include <iostream>
#include "json_parser.hpp"
#include "../include/path.hpp"

namespace nlohmann {
    inline void from_json(const json &j, TInputData &t) {
        j.at("points_count").get_to(t.points_count);
        j.at("agents_count").get_to(t.agents_count);

        if (j.contains("start_time")) {
            j.at("start_time").get_to(t.agent_start_time);
        } else {
            t.agent_start_time = decltype(t.agent_start_time)(t.agents_count, 0);
        }

        if (j.contains("depots")) {
            j.at("depots").get_to(t.agent_depots);
        } else {
            t.agent_depots = decltype(t.agent_depots)(t.agents_count, 0);
        }

        if (j.contains("depots_end")) {
            j.at("depots_end").get_to(t.agent_depots_end);
        } else {
            t.agent_depots_end.reserve(t.agent_depots.size());
            for (auto depot : t.agent_depots) {
                t.agent_depots_end.push_back(depot);
            }
        }

        for (auto depo : t.agent_depots) {
            t.depots_set.insert(depo);
        }

        for (auto depo : t.agent_depots_end) {
            t.depots_set.insert(depo);
        }

        j.at("min_load").get_to(t.min_load);
        j.at("max_load").get_to(t.max_load);
        j.at("max_time").get_to(t.max_time);
        j.at("max_distance").get_to(t.max_distance);
        j.at("distance_matrix").get_to(t.distance_matrix);
        j.at("time_matrix").get_to(t.time_matrix);
        j.at("point_scores").get_to(t.point_scores);
        j.at("point_service_times").get_to(t.point_service_times);
    }

    inline void to_json(json &j, const OutData &s) {
        j = json{
                {"route",          s.route},
                {"solution_size",  s.solution_size},
                {"total_time",     s.total_time},
                {"total_distance", s.total_distance},
                {"total_value",    s.total_value}
        };
    }

    inline void from_json(const json &j, OutData &s) {
        j.at("route").get_to(s.route);
        j.at("solution_size").get_to(s.solution_size);
        j.at("total_time").get_to(s.total_time);
        j.at("total_distance").get_to(s.total_distance);
        j.at("total_value").get_to(s.total_value);
    }
}

namespace JsonParser {

    using json = nlohmann::json;

    bool ParseInputDataFromJson(const std::string &jsonPath, TInputData &arg) {
        std::ifstream jsonFile(jsonPath);
        if (!jsonFile) {
            std::cerr << "Can`t open input file with problem" << std::endl;
            return false;
        }

        json j;
        jsonFile >> j;

        arg = j.get<TInputData>();
        return true;
    }

    bool ParseSolutionFromJson(const std::string &jsonPath, OutData &solution) {
        std::ifstream jsonFile(jsonPath);
        if (!jsonFile) {
            std::cerr << "Can`t open input file with solution" << std::endl;
            return false;
        }

        json j;
        jsonFile >> j;

        solution = j.get<OutData>();
        return true;
    }

    bool WriteSolutionToJsonFile(const std::string &jsonPath, OutData &&solution) {
        nlohmann::json j = std::move(solution);

        std::ofstream file(jsonPath);
        if (!file) {
            std::cerr << "Can`t open output file to write solution" << std::endl;
            return false;
        }

        file << j.dump(4);
        return true;
    };

    std::string MakeJsonPath(const std::string& base, const std::string& suffix) {
        if (base.empty()) {
            return suffix + ".json";
        }
        const auto dot  = base.rfind('.');
        const auto stem = (dot == std::string::npos) ? base : base.substr(0, dot);
        return stem + "_" + suffix + ".json";
    }

    bool WriteAgentsJson(const std::vector<TPath>& paths, const std::string& filepath) {
        json agents = json::array();

        for (size_t i = 0; i < paths.size(); ++i) {
            const auto& p = paths[i];

            std::vector<int> vertexes;
            vertexes.reserve(p.tour.size() + 2);
            vertexes.push_back(static_cast<int>(p.start_depo));
            for (auto v : p.tour) {
                vertexes.push_back(static_cast<int>(v));
            }
            vertexes.push_back(static_cast<int>(p.end_depo));

            agents.push_back(json{
                {"index",    static_cast<int>(i)},
                {"vertexes", std::move(vertexes)},
            });
        }

        json j;
        j["agents"] = std::move(agents);

        std::ofstream file(filepath);
        if (!file) {
            std::cerr << "Can`t open file for writing: " << filepath << "\n";
            return false;
        }
        file << j.dump(4);
        std::cout << "Written: " << filepath << "\n";
        return true;
    }
}