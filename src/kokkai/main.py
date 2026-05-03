import argparse


def run_ingest() -> None:
    print("ingest job is not implemented yet")


def main() -> None:
    parser = argparse.ArgumentParser(prog="kokkai")
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("ingest", help="run data ingestion")

    args = parser.parse_args()

    if args.command == "ingest":
        run_ingest()
        return

    parser.print_help()


if __name__ == "__main__":
    main()
