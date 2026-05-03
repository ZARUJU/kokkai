import argparse
import logging

from kokkai.ingest.cli_log import configure
from kokkai.ingest.cli_log import level_from_env
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
    args = parser.parse_args()

    if args.verbose:
        configure(logging.DEBUG)
    elif args.quiet:
        configure(logging.WARNING)
    else:
        configure(level_from_env())

    log = logging.getLogger(__name__)

    try:
        results = run(args.pipelines or None)
    except ValueError as error:
        log.error("ingest が失敗しました: %s", error)
        raise SystemExit(1) from error

    for result in results:
        line = f"ingested {result.name}: {result.count}"
        print(line)
        log.info("summary %s", line)


if __name__ == "__main__":
    main()
