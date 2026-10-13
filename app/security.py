"""Small, explicit request boundaries; no credentials or personal data in URLs."""
from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
from urllib.parse import urlsplit

from fastapi import HTTPException, Request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer


class FormSecurity:
    def __init__(self, secret: str):
        self.secret = secret.encode()
        self.signer = URLSafeTimedSerializer(secret, salt="aerzen-form-v1")

    def owner(self, request: Request) -> str:
        if "sid" not in request.session:
            request.session["sid"] = secrets.token_urlsafe(32)
        return hmac.new(self.secret, request.session["sid"].encode(), hashlib.sha256).hexdigest()

    def csrf(self, request: Request) -> str:
        if "csrf" not in request.session:
            request.session["csrf"] = secrets.token_urlsafe(32)
        return request.session["csrf"]

    def token(self, request: Request, purpose: str, **extra) -> str:
        return self.signer.dumps({"owner": self.owner(request), "purpose": purpose,
                                  "nonce": secrets.token_urlsafe(24), **extra})

    def verify(self, request: Request, fields: dict, purpose: str) -> dict:
        supplied = fields.get("csrf_token", "")
        expected = request.session.get("csrf", "")
        if not expected or not isinstance(supplied, str) or not hmac.compare_digest(supplied, expected):
            raise HTTPException(403, "Обновите страницу и повторите отправку.")
        # Origin is checked in addition to the synchronizer token when browsers send it.
        origin = request.headers.get("origin")
        if origin:
            incoming = urlsplit(origin)
            current = urlsplit(str(request.base_url))
            if (incoming.scheme, incoming.netloc) != (current.scheme, current.netloc):
                raise HTTPException(403, "Недопустимый источник запроса.")
        try:
            value = self.signer.loads(fields.get("form_token", ""), max_age=7200)
        except (BadSignature, SignatureExpired):
            raise HTTPException(403, "Обновите страницу: время формы истекло.")
        if value.get("owner") != self.owner(request) or value.get("purpose") != purpose:
            raise HTTPException(403, "Недопустимая форма.")
        return value

    def rate_key(self, request: Request, kind: str) -> str:
        # X-Forwarded-For is deliberately not trusted here. Deployment proxy handling is explicit.
        address = request.client.host if request.client else "unknown"
        return hmac.new(self.secret, f"{kind}:{address}".encode(), hashlib.sha256).hexdigest()


async def read_fields(request: Request, allowed: set[str]) -> dict[str, str]:
    content_type = request.headers.get("content-type", "").split(";", 1)[0].lower()
    if content_type != "application/x-www-form-urlencoded":
        raise HTTPException(415, "Эта форма принимает текстовые поля.")
    form = await request.form(max_fields=30, max_files=0)
    if len(form.multi_items()) != len(set(form.keys())):
        raise HTTPException(400, "Повторяющиеся поля не допускаются.")
    if set(form.keys()) - allowed:
        raise HTTPException(400, "В форме обнаружены неподдерживаемые поля.")
    fields = {}
    for key, value in form.items():
        if not isinstance(value, str):
            raise HTTPException(400, "Недопустимое поле.")
        fields[key] = value.strip()
    return fields


def clean_customer(fields: dict, *, order: bool = False) -> dict:
    bounds = {"name": (2, 100), "company": (0, 160), "email": (0, 254),
              "phone": (0, 40), "message": (0, 4000), "product_slug": (0, 100)}
    if order:
        bounds.update({"company": (2, 160), "inn": (10, 12), "delivery_address": (5, 600)})
    result = {}
    for key, (minimum, maximum) in bounds.items():
        value = fields.get(key, "")
        if not minimum <= len(value) <= maximum or any(ord(c) < 32 and c not in "\n\t" for c in value):
            raise HTTPException(422, "Проверьте длину и содержимое полей формы.")
        result[key] = value
    if result["email"] and not re.fullmatch(r"[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+", result["email"]):
        raise HTTPException(422, "Проверьте адрес электронной почты.")
    if result["phone"] and not re.fullmatch(r"[+()\d\s.\-]{7,40}", result["phone"]):
        raise HTTPException(422, "Проверьте номер телефона.")
    if not result["email"] and not result["phone"]:
        raise HTTPException(422, "Укажите телефон или электронную почту для ответа.")
    if order and result.get("inn") and not re.fullmatch(r"\d{10}|\d{12}", result["inn"]):
        raise HTTPException(422, "ИНН содержит 10 или 12 цифр.")
    if fields.get("consent") not in {"on", "true", "1", "yes"}:
        raise HTTPException(422, "Для отправки нужно согласие на обработку данных.")
    return result


def payload_digest(value: dict) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


class BodyLimitMiddleware:
    def __init__(self, app, max_bytes: int):
        self.app, self.max_bytes = app, max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        headers = dict(scope.get("headers", []))
        try:
            announced = int(headers.get(b"content-length", b"0"))
        except ValueError:
            announced = self.max_bytes + 1
        if announced > self.max_bytes:
            await send({"type": "http.response.start", "status": 413, "headers": [(b"content-type", b"text/plain; charset=utf-8")]})
            await send({"type": "http.response.body", "body": "Форма слишком большая.".encode()})
            return
        buffered, total = [], 0
        if scope.get("method") in {"POST", "PUT", "PATCH"}:
            while True:
                message = await receive()
                total += len(message.get("body", b""))
                if total > self.max_bytes:
                    await send({"type": "http.response.start", "status": 413, "headers": [(b"content-type", b"text/plain; charset=utf-8")]})
                    await send({"type": "http.response.body", "body": b"Request too large"})
                    return
                buffered.append(message)
                if not message.get("more_body"):
                    break
        async def wrapped_receive():
            return buffered.pop(0) if buffered else await receive()
        await self.app(scope, wrapped_receive, send)
