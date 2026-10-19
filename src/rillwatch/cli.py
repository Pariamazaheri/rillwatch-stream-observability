"""Local simulator, multi-source monitor, and reproducible CSV exports."""

import argparse
import asyncio
import json
from pathlib import Path

from .network import consume, serve
from .storage import Store


def main():
    parser = argparse.ArgumentParser(description="RillWatch stream observability")
    sub = parser.add_subparsers(dest="command", required=True)
    server = sub.add_parser("serve")
    server.add_argument("--host", default="127.0.0.1")
    server.add_argument("--port", type=int, default=9034)
    server.add_argument("--seed", type=int, default=42)
    server.add_argument("--stable", action="store_true")
    server.add_argument("--rate", type=float, default=40)
    live = sub.add_parser("monitor")
    live.add_argument(
        "--endpoint",
        action="append",
        required=True,
        help="Unique source=host:port; repeat for independent streams",
    )
    live.add_argument("--database", type=Path, required=True)
    live.add_argument("--duration", type=float, default=360)
    export = sub.add_parser("export")
    export.add_argument("--database", type=Path, required=True)
    export.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "serve":
        asyncio.run(serve(args.host, args.port, args.seed, not args.stable, args.rate))
    elif args.command == "monitor":
        endpoints = []
        for text in args.endpoint:
            try:
                source, address = text.split("=", 1)
                host, port = address.rsplit(":", 1)
                port = int(port)
                if not source or not host or not 0 < port < 65536:
                    raise ValueError
            except ValueError:
                parser.error("Endpoint must be source=host:port with valid port")
            endpoints.append((source, host, port))
        if len({e[0] for e in endpoints}) != len(endpoints):
            parser.error("Source names must be unique")
        print(
            json.dumps(
                asyncio.run(consume(endpoints, args.database, args.duration)), indent=2
            )
        )
    else:
        store = Store(args.database)
        try:
            store.export(args.output)
        finally:
            store.close()


if __name__ == "__main__":
    main()
