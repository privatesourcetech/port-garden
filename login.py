"""Login for Port Garden: first-run setup + signed session cookie, enforced at the ASGI layer
so it covers HTTP pages, NiceGUI static files and the socket.io websocket alike.

Credentials live in <data dir>/auth.json (the mounted ./output volume by default).
"""
from __future__ import annotations

import logging
import os
from html import escape
from http.cookies import SimpleCookie
from pathlib import Path
from urllib.parse import parse_qs

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse

import auth

log = logging.getLogger("port_garden.auth")

_PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Port Garden - Sign in</title>
<style>
body{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;background:#0f1319;
color:#e6ebf3;font:14px/1.45 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
form{background:#171d26;border:1px solid #2b3545;border-radius:10px;padding:28px;width:300px}
h1{font-size:17px;margin:0 0 18px}label{display:block;font-size:12px;color:#8c99ad;margin-bottom:12px}
input{display:block;width:100%;box-sizing:border-box;margin-top:4px;background:#0f1319;border:1px solid #2b3545;
border-radius:6px;padding:8px;color:#e6ebf3;font:inherit}
input:focus{outline:2px solid #4c8dff;outline-offset:-1px}
button{width:100%;margin-top:6px;background:#4c8dff;color:#06101f;border:0;border-radius:6px;padding:9px;
font:inherit;font-weight:600;cursor:pointer}
.err{color:#ff6b63;margin:0 0 12px;font-size:13px}
</style></head><body><form method="post" action="__ACTION__">
<h1>Port Garden</h1>__ERR__
__FIELDS__
<button type="submit">__BTN__</button></form></body></html>"""

_SIGNIN = """<label>Username<input name="username" autocomplete="username" autofocus required></label>
<label>Password<input name="password" type="password" autocomplete="current-password" required></label>"""

_SETUP = """<p style="color:#8c99ad;margin:0 0 14px">First run: create your login.</p>
<label>Username<input name="username" value="admin" autocomplete="username" required></label>
<label>Password (10+ characters)<input name="password" type="password" autocomplete="new-password" minlength="10" required autofocus></label>
<label>Repeat password<input name="password2" type="password" autocomplete="new-password" minlength="10" required></label>
__TOKEN__"""


_installed = False


def install(app: FastAPI, data_dir: Path) -> None:
    # NiceGUI re-executes app.py for every page view; install exactly once per process.
    global _installed
    if _installed:
        return
    _installed = True
    cfg = auth.Config(data_dir / "auth.json")
    throttle = auth.Throttle()

    def page(fields: str, button: str, action: str, error: str = "", status: int = 200) -> HTMLResponse:
        err = f'<p class="err">{escape(error)}</p>' if error else ""
        html = (_PAGE.replace("__FIELDS__", fields).replace("__BTN__", button)
                .replace("__ACTION__", action).replace("__ERR__", err))
        return HTMLResponse(html, status_code=status, headers={"Cache-Control": "no-store"})

    def setup_page(error: str = "", status: int = 200) -> HTMLResponse:
        token = ('<label>Setup token<input name="token" type="password" required></label>'
                 if cfg.setup_token else "")
        return page(_SETUP.replace("__TOKEN__", token), "Create login", "/setup", error, status)

    def login_page(error: str = "", status: int = 200) -> HTMLResponse:
        return page(_SIGNIN, "Sign in", "/login", error, status)

    def form(body: bytes) -> dict[str, str]:
        return {k: v[0] for k, v in parse_qs(body.decode("utf-8", "replace")).items()}

    def start_session(resp: RedirectResponse) -> RedirectResponse:
        resp.set_cookie(auth.COOKIE, auth.make_session(cfg), max_age=cfg.ttl, httponly=True,
                        samesite="strict", secure=cfg.cookie_secure, path="/")
        return resp

    def client_of(request: Request) -> str:
        return request.client.host if request.client else "?"

    @app.get("/healthz", include_in_schema=False)
    def healthz():
        return {"ok": True}

    @app.get("/setup", include_in_schema=False)
    def setup_form():
        return RedirectResponse("/login", status_code=303) if cfg.configured else setup_page()

    @app.post("/setup", include_in_schema=False)
    async def setup(request: Request):
        if cfg.configured:  # can never be re-run to overwrite the login
            return RedirectResponse("/login", status_code=303)
        if not auth.origin_ok(request.headers.get("origin"), request.headers.get("host")):
            return setup_page("Cross-origin request refused.", 403)
        client = client_of(request)
        wait = throttle.wait(client)
        if wait:
            return setup_page(f"Too many failed attempts. Try again in {wait}s.", 429)
        f = form(await request.body())
        user, pw = f.get("username", "").strip(), f.get("password", "")
        if cfg.setup_token and not auth.hmac.compare_digest(
                f.get("token", "").encode(), cfg.setup_token.encode()):
            throttle.fail(client)
            return setup_page("Wrong setup token.", 401)
        if not user or len(user) > 64:
            return setup_page("Enter a username (up to 64 characters).", 400)
        if len(pw) < 10:
            return setup_page("Password must be at least 10 characters.", 400)
        if pw != f.get("password2", ""):
            return setup_page("Passwords do not match.", 400)
        cfg.create(user, pw)
        log.warning("Admin login created via setup page (from %s)", client)
        return start_session(RedirectResponse("/", status_code=303))

    @app.get("/login", include_in_schema=False)
    def login_form(request: Request):
        if not cfg.configured:
            return RedirectResponse("/setup", status_code=303)
        if auth.read_session(cfg, request.cookies.get(auth.COOKIE)):
            return RedirectResponse("/", status_code=303)
        return login_page()

    @app.post("/login", include_in_schema=False)
    async def login(request: Request):
        if not cfg.configured:
            return RedirectResponse("/setup", status_code=303)
        if not auth.origin_ok(request.headers.get("origin"), request.headers.get("host")):
            return login_page("Cross-origin request refused.", 403)
        client = client_of(request)
        wait = throttle.wait(client)
        if wait:
            return login_page(f"Too many failed attempts. Try again in {wait}s.", 429)
        f = form(await request.body())
        pw_ok = auth.verify_password(f.get("password", ""), cfg.pw_hash)  # always hash: no timing leak
        user_ok = auth.hmac.compare_digest(f.get("username", "").encode(), cfg.username.encode())
        if not (pw_ok and user_ok):
            throttle.fail(client)
            log.warning("Failed login from %s", client)
            return login_page("Wrong username or password.", 401)
        throttle.ok(client)
        return start_session(RedirectResponse("/", status_code=303))

    @app.post("/logout", include_in_schema=False)
    def logout():
        resp = RedirectResponse("/login", status_code=303)
        resp.delete_cookie(auth.COOKIE, path="/")
        return resp

    app.add_middleware(_Gate, cfg=cfg)


class _Gate:
    """Pure ASGI middleware: HTTP *and* websocket requests need a session (except the public paths)."""

    def __init__(self, app, cfg: auth.Config) -> None:
        self.app, self.cfg = app, cfg

    async def __call__(self, scope, receive, send):
        kind = scope["type"]
        if kind not in ("http", "websocket"):
            return await self.app(scope, receive, send)
        path = scope["path"]
        if kind == "http" and path in auth.PUBLIC_PATHS:
            return await self.app(scope, receive, send)
        headers = {k.decode("latin-1"): v.decode("latin-1") for k, v in scope["headers"]}
        ok = False
        if self.cfg.configured:
            jar = SimpleCookie(headers.get("cookie", ""))
            morsel = jar.get(auth.COOKIE)
            ok = auth.read_session(self.cfg, morsel.value if morsel else None)
        if ok and kind == "http" and scope["method"] not in ("GET", "HEAD", "OPTIONS") \
                and not auth.origin_ok(headers.get("origin"), headers.get("host")):
            return await self._reply(send, 403, b"Cross-origin request refused")
        if ok and kind == "websocket" and not auth.origin_ok(headers.get("origin"), headers.get("host")):
            return await send({"type": "websocket.close", "code": 1008})
        if ok:
            return await self.app(scope, receive, send)
        if kind == "websocket":
            return await send({"type": "websocket.close", "code": 1008})
        target = "/login" if self.cfg.configured else "/setup"
        return await self._reply(send, 303, b"", [(b"location", target.encode())])

    @staticmethod
    async def _reply(send, status: int, body: bytes, extra=()):
        await send({"type": "http.response.start", "status": status,
                    "headers": [(b"content-type", b"text/plain"), (b"cache-control", b"no-store"), *extra]})
        await send({"type": "http.response.body", "body": body})
