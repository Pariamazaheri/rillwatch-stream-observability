"""Multi-source TCP client with bounded queues, framing and clean cancellation."""

import asyncio
import time
import uuid

from .engine import Engine
from .framing import Framer
from .simulator import Simulator
from .storage import Store


async def consume(endpoints, database, duration=360):
    if duration <= 0 or not endpoints:
        raise ValueError("Positive duration and endpoints required")
    queue = asyncio.Queue(maxsize=1000)
    start = time.monotonic()
    store = Store(database)
    engine = Engine(store)
    counters = {"connections": 0, "disconnects": 0, "idle_timeouts": 0}

    async def reader(source, host, port):
        while True:
            writer = None
            framer = Framer()
            sequence = 0
            epoch = uuid.uuid4().hex
            try:
                incoming, writer = await asyncio.wait_for(
                    asyncio.open_connection(host, port), 5
                )
                counters["connections"] += 1
                while True:
                    try:
                        chunk = await asyncio.wait_for(incoming.read(8192), 2)
                    except TimeoutError:
                        counters["idle_timeouts"] += 1
                        continue
                    if not chunk:
                        break
                    for frame in framer.feed(chunk):
                        await queue.put((source, epoch, sequence, frame))
                        sequence += 1
            except (OSError, TimeoutError):
                pass
            finally:
                for frame in framer.finish():
                    await queue.put((source, epoch, sequence, frame))
                    sequence += 1
                if writer:
                    writer.close()
                    try:
                        await writer.wait_closed()
                    except OSError:
                        pass
                counters["disconnects"] += 1
            await asyncio.sleep(0.2)

    tasks = [asyncio.create_task(reader(*endpoint)) for endpoint in endpoints]
    try:
        while time.monotonic() - start < duration:
            try:
                source, epoch, sequence, frame = await asyncio.wait_for(
                    queue.get(), 0.1
                )
                engine.ingest(source, epoch, sequence, time.monotonic() - start, frame)
            except TimeoutError:
                engine.tick(time.monotonic() - start)
    finally:
        for task in tasks:
            task.cancel()
        # Consume while readers finish, avoiding a full-queue shutdown deadlock.
        while not all(t.done() for t in tasks) or not queue.empty():
            try:
                source, epoch, sequence, frame = await asyncio.wait_for(
                    queue.get(), 0.1
                )
                engine.ingest(source, epoch, sequence, time.monotonic() - start, frame)
            except TimeoutError:
                pass
        await asyncio.gather(*tasks, return_exceptions=True)
        elapsed = time.monotonic() - start
        engine.finish(elapsed)
        result = {
            **counters,
            "duration_seconds": elapsed,
            "counts": store.counts(),
            "capacity_evictions": engine.monitor.cap_evictions,
        }
        store.close()
    return result


async def serve(host, port, seed=42, drift=True, rate=40):
    if rate <= 0:
        raise ValueError("rate must be positive")

    async def client(reader, writer):
        simulator = Simulator(seed=seed, drift=drift)
        start = time.monotonic()
        index = 0
        try:
            while True:
                writer.write(simulator.line(index, time.monotonic() - start))
                await writer.drain()
                index += 1
                await asyncio.sleep(1 / rate)
        except (OSError, asyncio.CancelledError):
            pass
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except OSError:
                pass

    server = await asyncio.start_server(client, host, port)
    async with server:
        await server.serve_forever()
