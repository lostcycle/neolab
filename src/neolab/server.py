import asyncio
import logging
from importlib import resources

from aiohttp import web

from neolab.broadcast import Broadcast
from neolab.executor import Executor
from neolab.workspace import Workspace
from neolab.ws_browser import ws_browser_handler
from neolab.ws_nvim import ws_nvim_handler

log = logging.getLogger(__name__)


async def health(request: web.Request) -> web.Response:
    return web.json_response({"ok": True, "service": "neolab"})


async def index(request: web.Request) -> web.Response:
    html = (resources.files("neolab") / "webui" / "index.html").read_text(encoding="utf-8")
    return web.Response(text=html, content_type="text/html")


async def _on_startup(app: web.Application) -> None:
    loop = asyncio.get_running_loop()
    app["executor"] = Executor(app["workspace"], app["broadcast"], loop)


async def _on_cleanup(app: web.Application) -> None:
    executor: Executor | None = app.get("executor")
    if executor is not None:
        executor.shutdown()


def build_app() -> web.Application:
    app = web.Application()
    app["workspace"] = Workspace()
    app["broadcast"] = Broadcast()
    app["executor"] = None  # populated in startup hook

    app.on_startup.append(_on_startup)
    app.on_cleanup.append(_on_cleanup)

    app.router.add_get("/", index)
    app.router.add_get("/api/health", health)
    app.router.add_get("/api/nvim", ws_nvim_handler)
    app.router.add_get("/api/browser", ws_browser_handler)

    webui_dir = resources.files("neolab") / "webui"
    app.router.add_static("/static/", path=str(webui_dir), show_index=False)
    return app


def run(host: str, port: int) -> None:
    app = build_app()
    log.info("neolab listening at http://%s:%d", host, port)
    web.run_app(app, host=host, port=port, print=None)
