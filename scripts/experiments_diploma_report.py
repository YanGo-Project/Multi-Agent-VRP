#!/usr/bin/env python3
"""
Анализ CSV в experiments/ и генерация сводных таблиц для диплома (LaTeX + CSV).

Сравнивает два подхода (например ma_benchmark vs tdtsp_benchmark): для каждой карты и каждого p
берёт **попарно совпадающие инстансы** (ключ из json_path: MA/TDTSP без суффиксов) и усредняет
sum_score, sum_distance, долю «успешных» строк (after_iterative_launch_ok в старых CSV; в узком CSV —
эвристика по feasible_agents_num).

Выход:
  - summary.txt   — краткая статистика по папкам в experiments/
  - table.tex     — tabular: датасет (multirow), карта, «пар», средние $|V|$ (points_count) и $k$ (число агентов),
                    затем метрики по $p$
  - table.csv     — то же в CSV
  - figures/<датасет>/<карта>/ — для каждого $p$ три линейных графика **только по инстансам этой карты**
                    (ось X: номера тестов 1…n после сортировки по instance_stem). Так не смешиваются разные
                    масштабы score/расстояния между картами на одной оси.
                    По умолчанию: --approach-a-dir = MA, --approach-b-dir = итеративный (TDTSP-PD).

Пример (по умолчанию читает experiments/ma_benchmark и experiments/tdtsp_benchmark):
  python3 scripts/experiments_diploma_report.py \\
    --dataset-name many \\
    --label-a MA-VRP --label-b "TDTSP-PD"

Явные каталоги и выход:
  python3 scripts/experiments_diploma_report.py \\
    --approach-a-dir experiments/ma_benchmark \\
    --approach-b-dir experiments/tdtsp_benchmark \\
    --out-dir experiments/diploma_tables \\
    --ps 0.1 0.2 0.5

Зависимости: pandas, matplotlib (опционально для графиков; при отсутствии — только таблица).
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path
from typing import Any

import pandas as pd

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from run_tdtsp_benchmark import (  # noqa: E402
    instance_join_key_from_json_path,
    map_name_from_json_path,
    p_value_from_json_path,
)


def dataset_tag_from_json_path(json_path: str) -> str:
    """Имя каталога набора после …/datasets/<tag>/… (many, one, …)."""
    s = json_path.replace("\\", "/")
    m = re.search(r"(?:^|/)datasets/([^/]+)/", s)
    return m.group(1) if m else "unknown"


def safe_dataset_dir(name: str) -> str:
    return re.sub(r"[^\w\-\.]+", "_", name).strip("_")[:64] or "dataset"


def p_file_tag(p: float) -> str:
    return f"p{int(round(float(p) * 100))}"


def pct_change_vs_iterative(ma_val: Any, iter_val: Any) -> float:
    """
    Относительное отклонение Multi-Agent от итеративного baseline:
      100 * (MA - iter) / |iter|

    При любом знаке score (в т.ч. отрицательном) в знаменателе |iter|, чтобы при отрицательном
    baseline масштаб оставался конечным и сопоставимым между инстансами.
    """
    try:
        ma_v = float(ma_val)
        it_v = float(iter_val)
    except (TypeError, ValueError):
        return float("nan")
    if math.isnan(ma_v) or math.isnan(it_v):
        return float("nan")
    if abs(it_v) < 1e-12:
        return float("nan")
    return 100.0 * (ma_v - it_v) / abs(it_v)


def pct_more_agents_vs_iterative(g_ma: Any, g_iter: Any) -> float:
    """100 * (g_ma - g_iter) / max(g_iter, ε); при g_iter≈0 и g_ma>0 → +100%."""
    try:
        gm = float(g_ma)
        gi = float(g_iter)
    except (TypeError, ValueError):
        return float("nan")
    if math.isnan(gm) or math.isnan(gi):
        return float("nan")
    if gi < 0.5:
        return 100.0 if gm > 0.5 else 0.0
    return 100.0 * (gm - gi) / gi


def good_agents_count(row: pd.Series, suf: str) -> float:
    """Число агентов с допустимым числом вершин (feasible_agents_num или разбор after_*)."""
    g = row.get(f"feasible_agents_num_{suf}")
    gi = pd.to_numeric(g, errors="coerce")
    if pd.notna(gi):
        return max(0.0, float(gi))

    k = row.get(f"agents_cnt_json_{suf}")
    if k is None or (isinstance(k, float) and pd.isna(k)):
        k = row.get(f"num_agents_run_{suf}")
    k = pd.to_numeric(k, errors="coerce")
    if pd.isna(k) or float(k) <= 0:
        return float("nan")

    nfile = pd.to_numeric(row.get(f"after_agents_in_file_{suf}"), errors="coerce")
    idle = pd.to_numeric(row.get(f"after_idle_agents_{suf}"), errors="coerce")
    bad = pd.to_numeric(row.get(f"after_vertex_bounds_violations_{suf}"), errors="coerce")
    if pd.isna(nfile):
        nfile = k
    idle = 0.0 if pd.isna(idle) else float(idle)
    bad = 0.0 if pd.isna(bad) else float(bad)
    return max(0.0, float(nfile) - idle - bad)


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def load_csv_dir(d: Path, tag: str) -> pd.DataFrame:
    paths = sorted(d.glob("*.csv"))
    if not paths:
        return pd.DataFrame()
    frames = []
    for p in paths:
        df = pd.read_csv(p)
        df["_from_csv"] = p.name
        frames.append(df)
    out = pd.concat(frames, ignore_index=True)
    out["_bench_tag"] = tag
    return out


def to_bool_ok(x: Any) -> bool:
    if pd.isna(x) or x == "":
        return False
    if isinstance(x, bool):
        return x
    s = str(x).strip().lower()
    return s in ("true", "1", "yes")


def prepare(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "json_path" not in out.columns:
        raise ValueError("CSV должен содержать столбец json_path")
    paths = out["json_path"].astype(str)
    out["map"] = paths.map(map_name_from_json_path)
    out["p"] = pd.to_numeric(paths.map(p_value_from_json_path), errors="coerce")
    out["instance_stem"] = paths.map(instance_join_key_from_json_path)

    score_col = "sum_score" if "sum_score" in out.columns else "total_score"
    out["total_score"] = pd.to_numeric(out[score_col], errors="coerce")
    out["sum_score"] = out["total_score"]

    out["sum_distance"] = pd.to_numeric(out["sum_distance"], errors="coerce")

    if "after_iterative_launch_ok" in out.columns:
        out["ok"] = out["after_iterative_launch_ok"].map(to_bool_ok)
    else:
        fa = pd.to_numeric(out.get("feasible_agents_num"), errors="coerce")
        out["ok"] = fa.fillna(0) > 0
    return out


def normalize_p(x: float) -> float:
    return round(float(x), 6)


def paired_aggregate(
    a: pd.DataFrame,
    b: pd.DataFrame,
    map_name: str,
    variant: str,
    p_val: float,
) -> dict[str, Any] | None:
    pa = a[(a["map"] == map_name) & (a["variant"] == variant)]
    pb = b[(b["map"] == map_name) & (b["variant"] == variant)]
    if pa.empty or pb.empty:
        return None
    pa = pa[pa["p"].apply(lambda x: not pd.isna(x) and normalize_p(x) == normalize_p(p_val))]
    pb = pb[pb["p"].apply(lambda x: not pd.isna(x) and normalize_p(x) == normalize_p(p_val))]
    if pa.empty or pb.empty:
        return None

    m = pd.merge(
        pa,
        pb,
        on=("instance_stem",),
        how="inner",
        suffixes=("_a", "_b"),
    )
    if m.empty:
        return None

    pc = (
        pd.to_numeric(m["points_count_a"], errors="coerce")
        if "points_count_a" in m.columns
        else pd.Series(dtype=float)
    )
    if "agents_cnt_json_a" in m.columns:
        ag = pd.to_numeric(m["agents_cnt_json_a"], errors="coerce")
    elif "agents_count_a" in m.columns:
        ag = pd.to_numeric(m["agents_count_a"], errors="coerce")
    elif "feasible_agents_num_a" in m.columns:
        ag = pd.to_numeric(m["feasible_agents_num_a"], errors="coerce")
    else:
        ag = pd.Series(dtype=float)
    vertices_mean = float(pc.mean()) if pc.notna().any() else float("nan")
    agents_mean = float(ag.mean()) if ag.notna().any() else float("nan")

    return {
        "n_pairs": len(m),
        "score_a": m["total_score_a"].mean(),
        "score_b": m["total_score_b"].mean(),
        "dist_a": m["sum_distance_a"].mean(),
        "dist_b": m["sum_distance_b"].mean(),
        "ok_a": 100.0 * m["ok_a"].mean(),
        "ok_b": 100.0 * m["ok_b"].mean(),
        "vertices_mean": vertices_mean,
        "agents_mean": agents_mean,
    }


def rel_diff_pct(score_a: float, score_b: float) -> float:
    if math.isnan(score_a) or math.isnan(score_b):
        return float("nan")
    if abs(score_b) < 1e-12:
        return float("nan")
    return 100.0 * (score_a - score_b) / abs(score_b)


def scan_experiments_root(root: Path) -> list[str]:
    lines: list[str] = []
    if not root.is_dir():
        return [f"Нет каталога: {root}"]
    lines.append(f"Корень: {root.resolve()}")
    for sub in sorted(root.iterdir()):
        if not sub.is_dir():
            continue
        csvs = list(sub.glob("*.csv"))
        if not csvs:
            continue
        rows = sum(len(pd.read_csv(f)) for f in csvs)
        maps = set()
        for f in csvs:
            try:
                df = pd.read_csv(f)
                if "map" in df.columns:
                    maps.update(df["map"].dropna().astype(str).unique())
                elif "json_path" in df.columns:
                    maps.update(
                        df["json_path"].astype(str).map(map_name_from_json_path).unique()
                    )
            except (ValueError, KeyError):
                pass
        lines.append(
            f"  {sub.name}/  CSV={len(csvs)}  строк≈{rows}  карты={sorted(maps)}"
        )
    return lines


def latex_escape(s: str) -> str:
    return (
        str(s)
        .replace("\\", "\\textbackslash{}")
        .replace("_", "\\_")
        .replace("%", "\\%")
        .replace("&", "\\&")
        .replace("#", "\\#")
    )


def fmt_num(x: float, nd: int = 1) -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "---"
    if abs(x) >= 1e5 or (abs(x) < 1e-3 and x != 0):
        return f"{x:.{nd}e}"
    if nd == 0:
        return f"{x:.0f}"
    return f"{x:.{nd}f}"


def fmt_int_or_dash(x: float) -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "---"
    return str(int(round(x)))


def fmt_dim(x: float) -> str:
    """Среднее число вершин/агентов: целое, если близко к int, иначе одна цифра."""
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "---"
    v = float(x)
    if abs(v - round(v)) < 0.05:
        return str(int(round(v)))
    return f"{v:.1f}"


def build_rows(
    da: pd.DataFrame,
    db: pd.DataFrame,
    maps: list[str],
    variant: str,
    ps: list[float],
) -> list[dict[str, Any]]:
    rows_out: list[dict[str, Any]] = []
    for map_name in maps:
        row: dict[str, Any] = {"map": map_name}
        meta_done = False
        for p in ps:
            agg = paired_aggregate(da, db, map_name, variant, p)
            key_p = str(normalize_p(p))
            if agg is None:
                row[f"score_a_{key_p}"] = float("nan")
                row[f"score_b_{key_p}"] = float("nan")
                row[f"dist_a_{key_p}"] = float("nan")
                row[f"dist_b_{key_p}"] = float("nan")
                row[f"ok_a_{key_p}"] = float("nan")
                row[f"ok_b_{key_p}"] = float("nan")
                row[f"dscore_{key_p}"] = float("nan")
                row[f"dok_{key_p}"] = float("nan")
                row[f"n_{key_p}"] = 0
                continue
            if not meta_done:
                row["vertices_mean"] = agg["vertices_mean"]
                row["agents_mean"] = agg["agents_mean"]
                meta_done = True
            row[f"score_a_{key_p}"] = agg["score_a"]
            row[f"score_b_{key_p}"] = agg["score_b"]
            row[f"dist_a_{key_p}"] = agg["dist_a"]
            row[f"dist_b_{key_p}"] = agg["dist_b"]
            row[f"ok_a_{key_p}"] = agg["ok_a"]
            row[f"ok_b_{key_p}"] = agg["ok_b"]
            row[f"dscore_{key_p}"] = rel_diff_pct(agg["score_a"], agg["score_b"])
            row[f"dok_{key_p}"] = agg["ok_a"] - agg["ok_b"]
            row[f"n_{key_p}"] = agg["n_pairs"]
        if not meta_done:
            row["vertices_mean"] = float("nan")
            row["agents_mean"] = float("nan")
        rows_out.append(row)
    return rows_out


def emit_latex(
    rows: list[dict[str, Any]],
    dataset_name: str,
    label_a: str,
    label_b: str,
    ps: list[float],
    caption: str,
    label: str,
) -> str:
    n_p = len(ps)
    inner = "llrrr" + ("rrrrrr" * n_p) + ("rr" * n_p)
    tabular_spec = "@{}" + inner + "@{}"
    n_ref_key = str(normalize_p(ps[0]))

    lines: list[str] = []
    lines.append("% Пакеты: \\usepackage{booktabs,multirow}")
    lines.append("\\begin{table*}[t]")
    lines.append("\\centering")
    lines.append("\\small")
    lines.append("\\setlength{\\tabcolsep}{2.8pt}")
    lines.append(f"\\caption{{{latex_escape(caption)}}}")
    lines.append(f"\\label{{{label}}}")
    lines.append(f"\\begin{{tabular}}{{{tabular_spec}}}")
    lines.append("\\toprule")

    h1_parts = [
        f"\\multicolumn{{5}}{{c}}{{{latex_escape('Датасет и карта')}}}",
    ]
    for p in ps:
        h1_parts.append(f"\\multicolumn{{6}}{{c}}{{$p = {p:g}$}}")
    for p in ps:
        h1_parts.append(
            f"\\multicolumn{{2}}{{c}}{{\\footnotesize "
            f"$\\Delta f$, $\\Delta$ усп. ($p={p:g}$)}}"
        )
    lines.append(" & ".join(h1_parts) + " \\\\")
    cmid = []
    col = 6
    for _ in ps:
        cmid.append(f"\\cmidrule(lr){{{col}-{col + 5}}}")
        col += 6
    for _ in ps:
        cmid.append(f"\\cmidrule(lr){{{col}-{col + 1}}}")
        col += 2
    lines.extend(cmid)

    h2 = ["", "", "", "", ""]
    for _ in ps:
        h2.append(f"\\multicolumn{{3}}{{c}}{{{latex_escape(label_a)}}}")
        h2.append(f"\\multicolumn{{3}}{{c}}{{{latex_escape(label_b)}}}")
    for _ in ps:
        h2.append("$\\Delta f$\\,\\%")
        h2.append("$\\Delta$~усп., п.п.")
    lines.append(" & ".join(h2) + " \\\\")
    cmid2 = []
    col = 6
    for _ in ps:
        cmid2.append(f"\\cmidrule(lr){{{col}-{col + 2}}}")
        cmid2.append(f"\\cmidrule(lr){{{col + 3}-{col + 5}}}")
        col += 6
    lines.extend(cmid2)

    h3 = [
        latex_escape("Набор"),
        latex_escape("Карта"),
        latex_escape("пар"),
        "$|V|$",
        "$k$",
    ]
    for _ in ps:
        h3.extend(
            [
                "$f$",
                "$L$",
                "усп.\\,\\%",
                "$f$",
                "$L$",
                "усп.\\,\\%",
            ]
        )
    for _ in ps:
        h3.extend(
            [
                "\\scriptsize к $f_B$",
                "\\scriptsize п.п.",
            ]
        )

    lines.append(" & ".join(h3) + " \\\\")
    lines.append("\\midrule")

    n_maps = len(rows)
    for i, r in enumerate(rows):
        n_inst = r.get(f"n_{n_ref_key}", 0)
        if isinstance(n_inst, float) and math.isnan(n_inst):
            n_inst = 0
        n_cell = fmt_int_or_dash(float(n_inst)) if n_inst else "---"

        if i == 0:
            ds_cell = f"\\multirow{{{n_maps}}}{{*}}{{{latex_escape(dataset_name)}}}"
        else:
            ds_cell = ""

        cells = [
            ds_cell,
            latex_escape(str(r["map"])),
            n_cell,
            fmt_dim(float(r.get("vertices_mean", float("nan")))),
            fmt_dim(float(r.get("agents_mean", float("nan")))),
        ]
        for p in ps:
            key = str(normalize_p(p))
            cells.append(fmt_num(r.get(f"score_a_{key}"), 1))
            cells.append(fmt_num(r.get(f"dist_a_{key}"), 0))
            cells.append(fmt_num(r.get(f"ok_a_{key}"), 0))
            cells.append(fmt_num(r.get(f"score_b_{key}"), 1))
            cells.append(fmt_num(r.get(f"dist_b_{key}"), 0))
            cells.append(fmt_num(r.get(f"ok_b_{key}"), 0))
        for p in ps:
            key = str(normalize_p(p))
            cells.append(fmt_num(r.get(f"dscore_{key}"), 1))
            cells.append(fmt_num(r.get(f"dok_{key}"), 1))
        lines.append(" & ".join(cells) + " \\\\")

    lines.append("\\bottomrule")
    lines.append("\\end{tabular}")
    lines.append("")
    lines.append(
        "\\begin{minipage}{\\linewidth}\\footnotesize"
        " \\textbf{Обозначения:} "
        " $f$~--- среднее \\texttt{sum\\_score} по попарным инстансам; "
        " $L$~--- среднее \\texttt{sum\\_distance}; "
        " усп.~--- доля «успешных» (\\texttt{after\\_iterative\\_launch\\_ok} или "
        " \\texttt{feasible\\_agents\\_num}${}>$0 в узком CSV); "
        " $\\Delta f$~--- $100(f_A-f_B)/|f_B|$, "
        f"$A=\\texttt{{{latex_escape(label_a)}}}$, "
        f"$B=\\texttt{{{latex_escape(label_b)}}}$; "
        " $\\Delta$~усп.~--- разница долей успешных (п.п.). "
        " Столбец \\textbf{пар}~--- число попарных инстансов для "
        f"$p={ps[0]:g}$ (первый из уровней в таблице). "
        " Столбцы $|V|$ и $k$~--- средние \\texttt{points\\_count} и "
        " \\texttt{feasible\\_agents\\_num} (или \\texttt{agents\\_cnt\\_json} в полном CSV) "
        " по тем же спаренным инстансам, "
        " что и для первого доступного уровня $p$ с непустым объединением. "
        "\\end{minipage}"
    )
    lines.append("\\end{table*}")

    return "\n".join(lines)


def collect_ma_vs_iter_per_instance(
    d_ma: pd.DataFrame,
    d_iter: pd.DataFrame,
    variant: str,
    ps: list[float],
) -> pd.DataFrame:
    """
    Спаренные инстансы: первый аргумент — Multi-Agent, второй — итеративный baseline (TDTSP).
    Колонки merge: *_ma / *_iter.
    """
    recs: list[dict[str, Any]] = []
    maps = sorted(set(d_ma["map"].unique()) & set(d_iter["map"].unique()))
    for map_name in maps:
        for p in ps:
            pv = normalize_p(p)
            pa = d_ma[(d_ma["map"] == map_name) & (d_ma["variant"] == variant)]
            pb = d_iter[(d_iter["map"] == map_name) & (d_iter["variant"] == variant)]
            pa = pa[
                pa["p"].apply(lambda x: not pd.isna(x) and normalize_p(x) == pv)
            ]
            pb = pb[
                pb["p"].apply(lambda x: not pd.isna(x) and normalize_p(x) == pv)
            ]
            if pa.empty or pb.empty:
                continue
            m = pd.merge(
                pa,
                pb,
                on="instance_stem",
                how="inner",
                suffixes=("_ma", "_iter"),
            )
            if m.empty:
                continue
            for _, row in m.iterrows():
                jp = str(
                    row.get("json_path_ma")
                    or row.get("json_path_iter")
                    or row.get("json_path_a")
                    or ""
                )
                ds = dataset_tag_from_json_path(jp)
                sc_ma = pd.to_numeric(
                    row.get("sum_score_ma", row.get("total_score_ma")), errors="coerce"
                )
                sc_it = pd.to_numeric(
                    row.get("sum_score_iter", row.get("total_score_iter")), errors="coerce"
                )
                d_ma_v = pd.to_numeric(row["sum_distance_ma"], errors="coerce")
                d_it_v = pd.to_numeric(row["sum_distance_iter"], errors="coerce")
                g_ma = good_agents_count(row, "ma")
                g_it = good_agents_count(row, "iter")
                recs.append(
                    {
                        "dataset": ds,
                        "map": map_name,
                        "p": pv,
                        "instance_stem": row["instance_stem"],
                        "pct_score": pct_change_vs_iterative(sc_ma, sc_it),
                        "pct_distance": pct_change_vs_iterative(d_ma_v, d_it_v),
                        "pct_agents_count": pct_more_agents_vs_iterative(g_ma, g_it),
                    }
                )
    out = pd.DataFrame(recs)
    if out.empty:
        return out
    out = out.sort_values(["dataset", "map", "p", "instance_stem"])
    out["_n"] = out.groupby(["dataset", "map", "p"], sort=False).cumcount() + 1
    out["plot_label"] = out["map"] + out["_n"].astype(str)
    return out.drop(columns=["_n"])


def emit_plots(
    d_ma: pd.DataFrame,
    d_iter: pd.DataFrame,
    variant: str,
    ps: list[float],
    label_ma: str,
    label_iter: str,
    out_dir: Path,
) -> list[str]:
    """
    Исследовательская логика: одна фигура — одна **карта** внутри датасета.

    Смешивание всех карт на одной оси X смешивает разные размеры инстансов и масштабы целевой
    функции; отдельный ряд по каждой карте даёт сопоставимый внутрисемейный профиль MA vs baseline.

    Для каждого (датасет, карта, p) — три PNG; ось X: номера тестов 1…n (сортировка instance_stem).

    Baseline = итеративный (d_iter), сравнение = Multi-Agent (d_ma).
    """
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError:
        return ["matplotlib не установлен — графики не созданы"]

    df = collect_ma_vs_iter_per_instance(d_ma, d_iter, variant, ps)
    if df.empty:
        return ["нет спаренных строк — графики не построены"]

    fig_root = out_dir / "figures"
    fig_root.mkdir(parents=True, exist_ok=True)
    written: list[str] = []

    score_note = (
        r"$100\,(s_{\mathrm{MA}} - s_{\mathrm{iter}})\,/\,|s_{\mathrm{iter}}|$ (\%)."
    )
    dist_note = (
        r"$100\,(L_{\mathrm{MA}} - L_{\mathrm{iter}})\,/\,|L_{\mathrm{iter}}|$ (\%)."
    )
    ag_note = (
        r"$100\,(g_{\mathrm{MA}} - g_{\mathrm{iter}})\,/\,\max(g_{\mathrm{iter}},\varepsilon)$ (\%); "
        r"$g$ — число агентов с допустимым числом вершин на маршруте."
    )

    for ds in sorted(df["dataset"].unique()):
        ds_dir = fig_root / safe_dataset_dir(str(ds))
        ds_dir.mkdir(parents=True, exist_ok=True)
        maps_here = sorted(df[df["dataset"] == ds]["map"].unique())

        for map_name in maps_here:
            map_dir = ds_dir / safe_dataset_dir(str(map_name))
            map_dir.mkdir(parents=True, exist_ok=True)

            for p in ps:
                pv = normalize_p(p)
                sub = df[
                    (df["dataset"] == ds)
                    & (df["map"] == map_name)
                    & (df["p"] == pv)
                ]
                if sub.empty:
                    continue
                sub = sub.sort_values("instance_stem").reset_index(drop=True)
                n_inst = len(sub)
                x = np.arange(n_inst)
                labs = [str(i + 1) for i in range(n_inst)]
                tag = p_file_tag(pv)
                wfig = max(7.5, min(28.0, 0.42 * max(n_inst, 1)))

                title_common = (
                    f"Датасет «{ds}», карта {map_name}, $p={pv:g}$\n"
                    f"baseline (итеративный): «{label_iter}»  →  Multi-Agent: «{label_ma}»\n"
                    f"Только инстансы этой карты: n={n_inst}, порядок по instance_stem"
                )

                def _line_png(y_col: str, fname: str, ylbl: str, note: str) -> None:
                    fig, ax = plt.subplots(figsize=(wfig, 4.9))
                    yv = pd.to_numeric(sub[y_col], errors="coerce").astype(float).values
                    ax.plot(x, yv, marker="o", linewidth=1.6, markersize=5, color="C0")
                    ax.axhline(0.0, color="k", linestyle="--", linewidth=0.75, alpha=0.5)
                    ax.set_xticks(x)
                    rot = 0 if n_inst <= 16 else 35
                    ax.set_xticklabels(labs, rotation=rot, ha="right" if rot else "center", fontsize=8)
                    ax.set_xlabel("Номер теста на карте (1 … n; сортировка по instance_stem)")
                    ax.set_ylabel(ylbl)
                    ax.grid(axis="y", alpha=0.3)
                    ax.set_title(title_common + "\n" + note, fontsize=9)
                    fig.tight_layout()
                    path = map_dir / fname
                    fig.savefig(path, dpi=160, bbox_inches="tight")
                    plt.close(fig)
                    written.append(str(path))

                _line_png(
                    "pct_score",
                    f"{tag}_score_pct_vs_iterative.png",
                    "Относительное изменение score (%)",
                    score_note,
                )
                _line_png(
                    "pct_distance",
                    f"{tag}_distance_pct_vs_iterative.png",
                    "Относительное изменение суммарной дистанции (%)",
                    dist_note,
                )
                _line_png(
                    "pct_agents_count",
                    f"{tag}_agents_ok_count_pct_vs_iterative.png",
                    "Относительное изменение числа агентов с допустимым числом вершин (%)",
                    ag_note,
                )

    return written


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Сводка experiments/ и LaTeX/CSV таблица для диплома."
    )
    ap.add_argument(
        "--experiments-root",
        type=Path,
        default=None,
        help="Для сводки по подпапкам (по умолчанию <repo>/experiments)",
    )
    ap.add_argument(
        "--approach-a-dir",
        type=Path,
        default=None,
        help="CSV Multi-Agent (по умолчанию experiments/ma_benchmark)",
    )
    ap.add_argument(
        "--approach-b-dir",
        type=Path,
        default=None,
        help="CSV итеративного baseline (по умолчанию experiments/tdtsp_benchmark)",
    )
    ap.add_argument("--label-a", type=str, default="MA-VRP")
    ap.add_argument("--label-b", type=str, default="TDTSP-PD")
    ap.add_argument("--dataset-name", type=str, default="many")
    ap.add_argument("--variant", type=str, default="demand", choices=("demand", "unit"))
    ap.add_argument(
        "--ps",
        type=float,
        nargs="+",
        default=[0.1, 0.2, 0.5],
        help="Уровни p (как в CSV)",
    )
    ap.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Папка для table.tex, table.csv, summary.txt (по умолчанию experiments/diploma_report)",
    )
    ap.add_argument("--caption", type=str, default="Сравнение подходов по картам и уровням $p$")
    ap.add_argument("--label", type=str, default="tab:bench_compare")
    ap.add_argument("--skip-scan", action="store_true", help="Не писать summary по корню experiments")
    ap.add_argument(
        "--no-plots",
        action="store_true",
        help="Не строить PNG (только таблицы и CSV)",
    )
    args = ap.parse_args()

    root = repo_root()
    exp = root / "experiments"
    if args.approach_a_dir is None:
        args.approach_a_dir = exp / "ma_benchmark"
    if args.approach_b_dir is None:
        args.approach_b_dir = exp / "tdtsp_benchmark"
    if args.out_dir is None:
        args.out_dir = exp / "diploma_report"

    exp_root = args.experiments_root or exp

    da = prepare(load_csv_dir(args.approach_a_dir.resolve(), "a"))
    db = prepare(load_csv_dir(args.approach_b_dir.resolve(), "b"))
    if da.empty or db.empty:
        print("Один из каталогов с CSV пуст.", file=sys.stderr)
        return 1

    da = da[da["variant"] == args.variant]
    db = db[db["variant"] == args.variant]
    maps = sorted(set(da["map"].unique()) & set(db["map"].unique()))
    if not maps:
        print(
            "Нет общих карт в двух наборах (проверьте variant и наличие CSV).",
            file=sys.stderr,
        )
        return 1

    rows = build_rows(da, db, maps, args.variant, args.ps)
    args.out_dir.mkdir(parents=True, exist_ok=True)

    # summary experiments root
    summary_lines = []
    if not args.skip_scan:
        summary_lines.extend(scan_experiments_root(exp_root))
        summary_lines.append("")
    summary_lines.append(
        f"Пары инстансов: merge по ключу из json_path (MA/TDTSP), variant={args.variant}"
    )
    summary_lines.append(f"Карты: {maps}")
    summary_lines.append(f"p: {args.ps}")
    (args.out_dir / "summary.txt").write_text("\n".join(summary_lines) + "\n", encoding="utf-8")

    # CSV wide
    csv_df = pd.DataFrame(rows)
    csv_df.insert(0, "dataset", args.dataset_name)
    nk0 = str(normalize_p(args.ps[0]))
    if f"n_{nk0}" in csv_df.columns:
        csv_df.insert(2, "pairs_ref_p", csv_df[f"n_{nk0}"])
    csv_df.to_csv(args.out_dir / "table.csv", index=False, encoding="utf-8")

    tex = emit_latex(
        rows,
        args.dataset_name,
        args.label_a,
        args.label_b,
        args.ps,
        args.caption,
        args.label,
    )
    (args.out_dir / "table.tex").write_text(tex, encoding="utf-8")

    meta = {
        "maps": maps,
        "ps": args.ps,
        "variant": args.variant,
        "rows": rows,
    }
    (args.out_dir / "table_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )

    plot_msgs: list[str] = []
    if not args.no_plots:
        plot_msgs = emit_plots(
            da,
            db,
            args.variant,
            args.ps,
            args.label_a,
            args.label_b,
            args.out_dir,
        )  # da=MA, db=итеративный baseline
        if plot_msgs:
            with open(args.out_dir / "figures_log.txt", "w", encoding="utf-8") as fl:
                fl.write("\n".join(plot_msgs) + "\n")

    print("\n".join(summary_lines))
    extra = f", figures/ ({len(plot_msgs)} файлов)" if plot_msgs and not args.no_plots else ""
    print(
        f"Записано: {args.out_dir / 'table.tex'}, table.csv, summary.txt{extra}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
