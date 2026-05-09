#!/usr/bin/env python3
"""
Приводит TOP-файлы (как в top_datasets/) к каноническому виду с баннером
«TOP test instances» и заголовками n / m / tmax.

Пример:
  python3 scripts/normalize_top_txt.py -i top_datasets/Set_21_234 -o datasets/top_normalized
  python3 scripts/normalize_top_txt.py -i top_datasets/Set_21_234/p2.2.c.txt --dry-run
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main() -> int:
    repo = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo / "scripts"))
    from top_instance_io import format_top_normalized, parse_top_path, validate_endpoints

    ap = argparse.ArgumentParser(description="Нормализация TOP .txt с баннером и проверками")
    ap.add_argument(
        "-i",
        "--input",
        type=Path,
        required=True,
        help="Файл .txt или каталог с рекурсивным поиском *.txt",
    )
    ap.add_argument(
        "-o",
        "--out-dir",
        type=Path,
        default=None,
        help="Корень выхода (сохраняется относительная структура каталогов)",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Только проверить разбор и замечания, не писать файлы",
    )
    ap.add_argument(
        "--warn-nonzero-endpoints",
        action="store_true",
        help="Печатать предупреждение, если S у старта/финиша не 0",
    )
    ap.add_argument(
        "--depot-loop",
        action="store_true",
        help="Одно депо: отбросить последнюю строку координат (фиктивный «финиш» в файле)",
    )
    args = ap.parse_args()

    inp = args.input.resolve()
    files: list[Path]
    if inp.is_file():
        files = [inp]
        base = inp.parent
    elif inp.is_dir():
        files = sorted(inp.rglob("*.txt"))
        base = inp
    else:
        print(f"Не найдено: {inp}", file=sys.stderr)
        return 1

    if not files:
        print(f"Нет *.txt под {inp}", file=sys.stderr)
        return 1

    ok = 0
    failed: list[tuple[Path, str]] = []
    for path in files:
        try:
            inst = parse_top_path(path, depot_loop=args.depot_loop)
            msgs = validate_endpoints(inst)
            if msgs and args.warn_nonzero_endpoints:
                print(f"{path}: предупреждение: {'; '.join(msgs)}", file=sys.stderr)
            text = format_top_normalized(inst)
            if args.dry_run:
                print(f"OK {path}")
                ok += 1
                continue
            if args.out_dir is None:
                print(f"Нужен --out-dir (или используйте --dry-run): {path}", file=sys.stderr)
                return 1
            out_root = args.out_dir.resolve()
            try:
                rel = path.relative_to(base)
            except ValueError:
                rel = Path(path.name)
            out_path = out_root / rel
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(text, encoding="utf-8")
            ok += 1
        except Exception as e:
            failed.append((path, str(e)))

    print(f"Готово: {ok} файлов", file=sys.stderr)
    for p, err in failed:
        print(f"Ошибка {p}: {err}", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
