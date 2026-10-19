"""Execute a real six-minute loopback run with a separately running producer."""

import asyncio
import json
from pathlib import Path

from rillwatch.network import consume, serve
from rillwatch.storage import Store


async def main():
    root = Path(__file__).resolve().parents[1]
    database = root / "data/runs/live.sqlite"
    database.parent.mkdir(parents=True, exist_ok=True)
    if database.exists():
        raise FileExistsError("Keep live evidence isolated; choose a fresh database")
    server = asyncio.create_task(serve("127.0.0.1", 19034, seed=42))
    await asyncio.sleep(0.2)
    if server.done():
        await server
    try:
        result = await consume([("synthetic", "127.0.0.1", 19034)], database, 360)
        store = Store(database)
        result["alert_count"] = store.db.execute(
            "SELECT COUNT(*) FROM alerts"
        ).fetchone()[0]
        result["report_count"] = store.db.execute(
            "SELECT COUNT(*) FROM reports"
        ).fetchone()[0]
        for table in ["reports", "alerts"]:
            rows = [
                json.loads(row[0])
                for row in store.db.execute(f"SELECT payload FROM {table} ORDER BY id")
            ]
            filename = "live_windows.json" if table == "reports" else "live_alerts.json"
            (root / "reports" / filename).write_text(json.dumps(rows, indent=2) + "\n")
        store.export(root / "data/runs/live_exports")
        store.close()
        (root / "reports/live_run.json").write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result, indent=2), flush=True)
    finally:
        server.cancel()
        await asyncio.gather(server, return_exceptions=True)


if __name__ == "__main__":
    asyncio.run(main())
