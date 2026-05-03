import argparse

from kokkai.ingest.runner import PIPELINES
from kokkai.ingest.runner import run


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "pipelines",
        nargs="*",
        help=f"取り込む pipeline 名。省略時は全件実行。利用可能: {', '.join(sorted(PIPELINES))}",
    )
    args = parser.parse_args()

    try:
        results = run(args.pipelines or None)
    except ValueError as error:
        parser.error(str(error))

    for result in results:
        print(f"ingested {result.name}: {result.count}")


if __name__ == "__main__":
    main()
