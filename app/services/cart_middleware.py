from __future__ import annotations

import uuid
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

CART_COOKIE = "mf_cart"
CART_MAX_AGE = 3600


class CartSessionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        session_id = request.cookies.get(CART_COOKIE)
        if not session_id:
            session_id = str(uuid.uuid4())
            request.state.session_id = session_id
            response: Response = await call_next(request)
            response.set_cookie(
                key=CART_COOKIE,
                value=session_id,
                max_age=CART_MAX_AGE,
                path="/",
                httponly=True,
            )
            return response
        request.state.session_id = session_id
        return await call_next(request)
