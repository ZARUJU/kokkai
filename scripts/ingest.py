import argparse
import logging

from kokkai.ingest.cli_log import configure
from kokkai.ingest.cli_log import level_from_env
from kokkai.ingest.cli_sessions import build_run_context
from kokkai.ingest.runner import PIPELINES
from kokkai.ingest.runner import run


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "pipelines",
        nargs="*",
        help=f"取り込む pipeline 名。省略時は全件実行。利用可能: {', '.join(sorted(PIPELINES))}",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="デバッグ寄りのログ（logging.DEBUG）",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="警告のみ（logging.WARNING）。--verbose と同時指定した場合は verbose が優先",
    )
    parser.add_argument(
        "--session",
        dest="sessions",
        action="append",
        metavar="NUM[,NUM...]",
        default=None,
        help=(
            "対象国会回次。shugiin_bills / kokkai_meetings / questions に適用（複数回指定可・"
            "各値はカンマ区切り可）。省略時は各 pipeline の環境変数または DB に従う"
        ),
    )
    args = parser.parse_args()

    if args.verbose:
        configure(logging.DEBUG)
    elif args.quiet:
        configure(logging.WARNING)
    else:
        configure(level_from_env())

    log = logging.getLogger(__name__)

    try:
        results = run(
            args.pipelines or None,
            context=build_run_context(args.sessions),
        )
    except ValueError as error:
        log.error("ingest が失敗しました: %s", error)
        raise SystemExit(1) from error

    for result in results:
        line = f"ingested {result.name}: {result.count}"
        print(line)
        log.info("summary %s", line)


if __name__ == "__main__":
    main()
