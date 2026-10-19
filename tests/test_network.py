"""Small real loopback tests; no external services or fixed TCP ports."""

import asyncio
import json

from rillwatch.network import consume
from rillwatch.simulator import Simulator
from rillwatch.storage import Store


def test_two_sources_fragmented_utf8_and_idle_reporting(tmp_path):
    async def scenario():
        line = Simulator(corruption=0).line(0, 0)

        async def peer(reader, writer):
            try:
                writer.write(line[:10])
                await writer.drain()
                await asyncio.sleep(0.01)
                writer.write(line[10:])
                await writer.drain()
                await asyncio.sleep(3)
            finally:
                writer.close()
                await writer.wait_closed()

        server = await asyncio.start_server(peer, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        async with server:
            result = await consume(
                [("a", "127.0.0.1", port), ("b", "127.0.0.1", port)],
                tmp_path / "events.sqlite",
                0.3,
            )
        assert result["counts"] == {"clean": 2}
        store = Store(tmp_path / "events.sqlite")
        assert (
            store.db.execute("SELECT COUNT(DISTINCT source) FROM events").fetchone()[0]
            == 2
        )
        report = json.loads(
            store.db.execute("SELECT payload FROM reports").fetchone()[0]
        )
        assert report["window_total"] == 2 and report["partial"]
        store.close()

    asyncio.run(scenario())


def test_reconnect_quarantines_partial_before_new_connection(tmp_path):
    async def scenario():
        connections = 0

        async def peer(reader, writer):
            nonlocal connections
            connections += 1
            writer.write(
                b'{"broken":'
                if connections == 1
                else Simulator(corruption=0).line(0, 0)
            )
            await writer.drain()
            writer.close()
            await writer.wait_closed()

        server = await asyncio.start_server(peer, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        async with server:
            result = await consume(
                [("a", "127.0.0.1", port)], tmp_path / "events.sqlite", 0.35
            )
        assert result["counts"]["bad"] == 1
        assert result["counts"]["clean"] >= 1
        assert result["connections"] >= 2

    asyncio.run(scenario())
