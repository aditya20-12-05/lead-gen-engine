"""Command line: python -m engine {serve,seed,check-sources}."""

import argparse

from . import create_app, db, seed, sources


def main():
    parser = argparse.ArgumentParser(prog="python -m engine")
    parser.add_argument("--db", default="data/engine.db")
    parser.add_argument("--settings", default="data/settings.json")
    sub = parser.add_subparsers(dest="command", required=True)
    serve = sub.add_parser("serve", help="Run the app on this computer only")
    serve.add_argument("--port", type=int, default=5050)
    sub.add_parser("seed", help="Load the Gulf community bodies starting list")
    sub.add_parser("check-sources", help="Fetch every source page and record its status")
    args = parser.parse_args()

    app = create_app(args.db, args.settings)
    if args.command == "serve":
        # Bound to localhost: the app is never exposed to the network.
        app.run(host="127.0.0.1", port=args.port)
        return
    with db.connect(args.db) as conn:
        if args.command == "seed":
            print(f"Added {seed.seed(conn)} organisations.")
        elif args.command == "check-sources":
            for name, url, status in sources.check_all(conn):
                print(f"{status:<40} {name}  {url}")


if __name__ == "__main__":
    main()
