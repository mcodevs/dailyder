from __future__ import annotations

from aiohttp import web

from dailyder_bot.db.session import DatabaseSessionManager


class HealthServer:
    def __init__(self, db: DatabaseSessionManager, port: int) -> None:
        self.db = db
        self.port = port
        self._runner: web.AppRunner | None = None

    async def start(self) -> None:
        app = web.Application()
        app.router.add_get("/healthz", self._handle_health)
        self._runner = web.AppRunner(app)
        await self._runner.setup()
        site = web.TCPSite(self._runner, host="0.0.0.0", port=self.port)
        await site.start()

    async def stop(self) -> None:
        if self._runner is not None:
            await self._runner.cleanup()

    async def _handle_health(self, request: web.Request) -> web.Response:
        try:
            await self.db.ping()
        except Exception as exc:
            return web.json_response({"status": "error", "detail": str(exc)}, status=503)
        return web.json_response({"status": "ok"})

