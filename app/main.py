"""Server-rendered public catalogue and guarded lead/order workflows."""
from __future__ import annotations

import html
import json
import logging
import secrets
import time
import uuid
from types import SimpleNamespace
from typing import Literal
from xml.etree.ElementTree import Element, SubElement, tostring

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from jinja2 import TemplateNotFound
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.gzip import GZipMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from .config import Settings
from .content import Content, commercial_product, format_rub, price_kopecks, readiness
from .database import DuplicateConflict, Store
from .security import BodyLimitMiddleware, FormSecurity, clean_customer, payload_digest, read_fields


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    app = FastAPI(title="AERZEN / ПСК АРУС", docs_url=None, redoc_url=None, openapi_url=None)
    content = Content(settings.root_dir)
    store = Store(settings.data_dir)
    security = FormSecurity(settings.secret_key)
    templates = Jinja2Templates(directory=settings.root_dir / "templates")
    templates.env.filters["rub"] = format_rub
    app.state.settings, app.state.store, app.state.content, app.state.security = settings, store, content, security
    static_dir = settings.root_dir / "static"
    static_dir.mkdir(exist_ok=True)
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
    app.add_middleware(SessionMiddleware, secret_key=settings.secret_key, session_cookie="aerzen_session",
                       max_age=settings.session_max_age, same_site="lax", https_only=settings.secure_cookies)
    app.add_middleware(BodyLimitMiddleware, max_bytes=settings.max_body_bytes)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=list(settings.allowed_hosts))
    app.add_middleware(GZipMiddleware, minimum_size=1000)

    @app.middleware("http")
    async def headers(request: Request, call_next):
        request.state.csp_nonce = secrets.token_urlsafe(18)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; base-uri 'self'; object-src 'none'; frame-ancestors 'none'; "
            f"script-src 'self' 'nonce-{request.state.csp_nonce}'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; font-src 'self'; connect-src 'self'; form-action 'self'; frame-src 'none'")
        if settings.secure_cookies and settings.base_url.startswith("https:"):
            response.headers["Strict-Transport-Security"] = "max-age=31536000"
        if request.url.path.startswith(("/cart", "/checkout", "/orders", "/requests")):
            response.headers["Cache-Control"] = "no-store"
            response.headers["X-Robots-Tag"] = "noindex, nofollow"
        elif settings.preview_mode:
            response.headers["X-Robots-Tag"] = "noindex, nofollow"
        return response

    def base_context(request: Request, purpose: str = "lead") -> dict:
        site = content.site
        return {"request": request, "site": site, "products": content.products, "articles": content.articles,
                "alternatives": content.alternatives,
                "csrf_token": security.csrf(request), "form_token": security.token(request, purpose),
                "cart_token": security.token(request, "cart"), "csp_nonce": request.state.csp_nonce,
                "preview_mode": settings.preview_mode, "readiness": readiness(site, settings),
                "cart_count": sum(int(q) for q in request.session.get("cart", {}).values()),
                "canonical_url": settings.base_url + request.url.path}

    def render(request: Request, name: str, status_code: int = 200, purpose: str = "lead", **values):
        context = {**base_context(request, purpose), **values}
        try:
            return templates.TemplateResponse(request=request, name=name, context=context, status_code=status_code)
        except TemplateNotFound:
            # During frontend integration, errors remain understandable and HTML-escaped.
            title = html.escape(str(values.get("title", values.get("message", "Страница готовится"))))
            return HTMLResponse(f"<!doctype html><html lang='ru'><meta charset='utf-8'><title>{title}</title><h1>{title}</h1><a href='/'>Главная</a></html>", status_code=status_code)

    def rate_allowed(request: Request, kind: str, limit: int, window: int) -> bool:
        # Per-session limit plus a broader network limit prevents a shared company NAT address
        # from giving every visitor the same small request allowance.
        return (store.consume_rate(kind+":"+security.owner(request),limit,window)
                and store.consume_rate(security.rate_key(request,kind),limit*10,window))

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException):
        message = exc.detail if isinstance(exc.detail, str) else "Не удалось выполнить запрос."
        return render(request, "error.html", status_code=exc.status_code, title=message, message=message)

    @app.exception_handler(Exception)
    async def unexpected(request: Request, exc: Exception):
        logging.getLogger("aerzen.security").error("Request failed safely: %s", type(exc).__name__)
        return render(request, "error.html", status_code=500, title="Не удалось выполнить запрос", message="Повторите позже или свяжитесь с компанией.")

    @app.get("/healthz")
    async def health():
        return JSONResponse({"status": "ok"})

    @app.get("/", response_class=HTMLResponse)
    async def home(request: Request):
        return render(request, "index.html", page="home")

    @app.get("/models", response_class=HTMLResponse)
    async def models(request: Request, q: str = Query(default="", max_length=100),
                     equipment_type: Literal["", "rotary", "screw"] = Query(default="", alias="type"),
                     equipment_kind: Literal["", "reference", "series", "model"] = Query(default="", alias="kind"),
                     brand: Literal["", "huadong", "mingtian", "erstvak", "aerzen"] = Query(default="")):
        query = q.strip()
        matching_references = []
        if brand != "aerzen" and equipment_type != "screw" and equipment_kind in ("", "reference"):
            for family in content.alternatives:
                family_brand = family["slug"].split("-")[0]
                if brand and family_brand != brand:
                    continue
                for model in family["models"]:
                    searchable = " ".join((model["name"], family["name"], family["manufacturer"],
                                           family["technology"])).casefold()
                    if query.casefold() in searchable:
                        matching_references.append({
                            "family": family, "model": model, "brand": family_brand,
                            "card_id": f"ref-{family['slug']}-{model['anchor']}",
                            "url": f"/alternatives/{family['slug']}#{model['anchor']}",
                        })
        matching = []
        for product in content.products:
            if brand not in ("", "aerzen") or equipment_kind == "reference":
                continue
            searchable = " ".join(str(product.get(key, "")) for key in ("brand", "name", "type", "family")).casefold()
            if query.casefold() not in searchable:
                continue
            if equipment_type == "rotary" and "Роторная" not in product.get("type", ""):
                continue
            if equipment_type == "screw" and "Винтов" not in product.get("type", ""):
                continue
            if equipment_kind == "series" and not product.get("is_series"):
                continue
            if equipment_kind == "model" and product.get("is_series"):
                continue
            matching.append(product)
        return render(request, "models.html", page="models", title="Каталог воздуходувок и компрессоров", query=query,
                      equipment_type=equipment_type, equipment_kind=equipment_kind, selected_brand=brand,
                      matching_products=matching, matching_references=matching_references)

    @app.get("/alternatives", response_class=HTMLResponse)
    async def alternatives(request: Request):
        return render(request, "alternatives.html", page="alternatives",
                      title="Китайские воздуходувки и модели ERSTVAK: подбор альтернативы")

    @app.get("/alternatives/{slug}", response_class=HTMLResponse)
    async def alternative(request: Request, slug: str):
        family = content.alternative(slug)
        if family is None:
            raise HTTPException(404, "Справочная серия не найдена")
        message = (f"Рассматриваю {family['name']}. Нужна альтернатива AERZEN.\n"
                   "Модель: \nРасход воздуха: \nПерепад давления: \nРежим работы: ")
        return render(request, "alternative.html", page="alternatives", family=family,
                      message_default=message, title=family["title"])

    @app.get("/models/{slug}", response_class=HTMLResponse)
    async def model(request: Request, slug: str):
        product = content.product(slug)
        if not product:
            raise HTTPException(404, "Модель не найдена")
        products = content.products
        index = next(i for i, p in enumerate(products) if p["slug"] == slug)
        return render(request, "product.html", page="models", product=product, title=product.get("name", slug),
                      next_product=products[(index+1) % len(products)] if len(products)>1 else None,
                      previous_product=products[(index-1) % len(products)] if len(products)>1 else None,
                      purchasable=readiness(content.site,settings)["commerce_enabled"] and commercial_product(product))

    @app.get("/solutions", response_class=HTMLResponse)
    async def solutions(request: Request):
        return render(request, "solutions.html", page="solutions", kind="task", title="Есть задача")

    @app.get("/repair", response_class=HTMLResponse)
    async def repair(request: Request):
        return render(request, "repair.html", page="repair", kind="repair", title="Ремонт и диагностика")

    @app.get("/about", response_class=HTMLResponse)
    async def about(request: Request):
        return render(request, "about.html", page="about", title="О компании")

    @app.get("/contact", response_class=HTMLResponse)
    async def contact(request: Request):
        return render(request, "contact.html", page="contact", kind="contact", title="Контакты")

    @app.get("/articles", response_class=HTMLResponse)
    async def articles(request: Request):
        return render(request, "articles.html", page="articles", title="Статьи и применение")

    @app.get("/articles/{slug}", response_class=HTMLResponse)
    async def article(request: Request, slug: str):
        item = next((a for a in content.articles if a["slug"]==slug),None)
        if not item:
            raise HTTPException(404, "Статья не найдена")
        return render(request,"article.html", page="articles", article=item, title=item.get("title",slug))

    def register_legal_page(page_key: str):
        async def legal(request: Request):
            return render(request, "legal.html", page="legal", legal_page=page_key, page_key=page_key)
        app.add_api_route("/"+page_key, legal, methods=["GET"], response_class=HTMLResponse, name=page_key)
    for page_key in ("privacy", "terms", "payment", "delivery", "cookies"):
        register_legal_page(page_key)

    @app.post("/requests/{kind}")
    async def submit_lead(request: Request, kind: str):
        if kind not in {"task", "repair", "quote", "contact"}:
            raise HTTPException(404, "Форма не найдена")
        fields = await read_fields(request,{"name","company","email","phone","message","product_slug","consent","website","csrf_token","form_token"})
        token = security.verify(request,fields,"lead")
        if not readiness(content.site,settings)["forms_enabled"]:
            raise HTTPException(503, "Форма пока не подключена. Используйте контакты компании.")
        if not rate_allowed(request,"lead",settings.rate_limit,settings.rate_window_seconds):
            raise HTTPException(429, "Слишком много обращений. Повторите позже.")
        if fields.get("website"):
            return render(request,"request_received.html", title="Запрос принят", kind=kind)
        customer = clean_customer(fields)
        if customer["product_slug"] and not content.product(customer["product_slug"]):
            raise HTTPException(422, "Выберите существующую модель")
        record = {"id":uuid.uuid4().hex,"owner_hash":security.owner(request),"nonce":token["nonce"],
                  "payload_hash":payload_digest({"kind":kind,**customer}),"kind":kind,"payload":customer,
                  "policy_version":str(content.site.get("legal",{}).get("privacy_version","")),"created_at":int(time.time())}
        try:
            saved, created = store.save_lead(record)
        except DuplicateConflict:
            raise HTTPException(409,"Форма уже использована. Обновите страницу для нового обращения.")
        return render(request,"request_received.html",title="Запрос принят",kind=kind,request_id=saved["id"],duplicate=not created)

    def cart_items(request: Request) -> list[dict]:
        items = []
        for slug, quantity in request.session.get("cart",{}).items():
            product=content.product(slug)
            if product and commercial_product(product) and isinstance(quantity,int) and 1 <= quantity <= 10:
                price = price_kopecks(product)
                items.append({"slug":slug,"sku":product["sku"],"name":product.get("name",slug),"quantity":quantity,
                              "unit_kopecks":price,"total_kopecks":price*quantity,"product":product})
        return items

    def require_commerce():
        if not readiness(content.site,settings)["commerce_enabled"]:
            raise HTTPException(503,"Онлайн-заказ пока не подключён. Запросите предложение у компании.")

    @app.get("/cart", response_class=HTMLResponse)
    async def cart(request: Request):
        items=cart_items(request)
        return render(request,"cart.html",page="cart",purpose="cart",items=items,total_kopecks=sum(i["total_kopecks"] for i in items))

    @app.post("/cart/add")
    async def cart_add(request: Request):
        fields=await read_fields(request,{"slug","quantity","csrf_token","form_token"})
        security.verify(request,fields,"cart")
        require_commerce()
        product=content.product(fields.get("slug",""))
        if not product or not commercial_product(product):
            raise HTTPException(422,"Эта модель доступна по запросу.")
        try:
            quantity=int(fields.get("quantity","1"))
        except ValueError:
            raise HTTPException(422,"Проверьте количество.")
        if not 0 <= quantity <= 10:
            raise HTTPException(422,"Количество должно быть от 0 до 10.")
        current=dict(request.session.get("cart",{}))
        if quantity:
            current[product["slug"]]=quantity
        else:
            current.pop(product["slug"],None)
        request.session["cart"]=current
        return RedirectResponse("/cart",status_code=303)

    @app.get("/checkout", response_class=HTMLResponse)
    async def checkout(request: Request):
        require_commerce()
        items=cart_items(request)
        if not items:
            return RedirectResponse("/cart",status_code=303)
        snapshot=[{k:i[k] for k in ("slug","quantity","unit_kopecks")} for i in items]
        return render(request,"checkout.html",page="checkout",items=items,total_kopecks=sum(i["total_kopecks"] for i in items),
                      form_token=security.token(request,"order",items=snapshot))

    @app.post("/checkout")
    async def submit_order(request: Request):
        fields=await read_fields(request,{"name","company","email","phone","message","inn","delivery_address","consent","website","csrf_token","form_token"})
        token=security.verify(request,fields,"order")
        require_commerce()
        if fields.get("website"):
            raise HTTPException(422,"Не удалось оформить заказ.")
        if not rate_allowed(request,"order",4,3600):
            raise HTTPException(429,"Слишком много заказов. Повторите позже.")
        buyer=clean_customer(fields,order=True)
        items=[]
        for original in token.get("items",[]):
            product=content.product(original["slug"])
            if not product or not commercial_product(product) or price_kopecks(product)!=original["unit_kopecks"]:
                raise HTTPException(409,"Данные товара изменились. Обновите корзину.")
            items.append({"slug":product["slug"],"sku":product["sku"],"name":product.get("name",product["slug"]),
                          "quantity":original["quantity"],"unit_kopecks":original["unit_kopecks"],
                          "total_kopecks":original["quantity"]*original["unit_kopecks"]})
        if not items:
            raise HTTPException(422,"Корзина пуста.")
        record={"id":uuid.uuid4().hex,"owner_hash":security.owner(request),"nonce":token["nonce"],"buyer":buyer,"items":items,
                "total_kopecks":sum(i["total_kopecks"] for i in items),"seller_snapshot":content.site["seller"],
                "payload_hash":payload_digest({"buyer":buyer,"items":items}),"created_at":int(time.time()),
                "policy_version":str(content.site.get("legal",{}).get("privacy_version",""))}
        try:
            saved, _ = store.save_order(record)
        except DuplicateConflict:
            raise HTTPException(409,"Форма уже использована. Обновите страницу.")
        request.session["cart"]={}
        return RedirectResponse(f"/orders/{saved['id']}",status_code=303)

    def owned_order(request: Request, public_id: str) -> dict:
        if len(public_id)!=32 or not all(c in "0123456789abcdef" for c in public_id):
            raise HTTPException(404,"Заказ не найден")
        order=store.order_for_owner(public_id,security.owner(request))
        if not order:
            raise HTTPException(404,"Заказ не найден")
        return order

    @app.get("/orders/{public_id}", response_class=HTMLResponse)
    async def order(request: Request, public_id: str):
        return render(request,"order.html",page="order",order=SimpleNamespace(**owned_order(request,public_id)),
                      invoice_url=f"/orders/{public_id}/invoice")

    @app.get("/orders/{public_id}/invoice", response_class=HTMLResponse)
    async def invoice(request: Request, public_id: str):
        order=owned_order(request,public_id)
        require_commerce()
        return render(request,"invoice.html",page="invoice",order=SimpleNamespace(**order),seller=order["seller_snapshot"])

    @app.get("/robots.txt")
    async def robots():
        body="User-agent: *\nDisallow: /\n" if settings.preview_mode else "User-agent: *\nDisallow: /cart\nDisallow: /checkout\nDisallow: /orders/\nDisallow: /requests/\nSitemap: "+settings.base_url+"/sitemap.xml\n"
        return Response(body,media_type="text/plain")

    @app.get("/sitemap.xml")
    async def sitemap():
        tree=Element("urlset",xmlns="http://www.sitemaps.org/schemas/sitemap/0.9")
        urls=["/","/models","/solutions","/repair","/about","/articles","/contact","/alternatives"]
        urls += ["/alternatives/"+family["slug"] for family in content.alternatives]
        urls += ["/models/"+p["slug"] for p in content.products] + ["/articles/"+a["slug"] for a in content.articles]
        if not settings.preview_mode:
            for url in urls:
                SubElement(SubElement(tree,"url"),"loc").text=settings.base_url+url
        return Response(tostring(tree,encoding="utf-8",xml_declaration=True),media_type="application/xml")

    @app.get("/feed.xml")
    async def feed():
        require_commerce()
        eligible=[p for p in content.products if commercial_product(p)]
        if not eligible:
            raise HTTPException(404,"Подтверждённых товаров пока нет")
        tree=Element("yml_catalog",date=time.strftime("%Y-%m-%d %H:%M"))
        shop=SubElement(tree,"shop")
        SubElement(shop,"name").text=content.site.get("name","ПСК АРУС")
        SubElement(shop,"company").text=content.site["seller"]["legal_name"]
        SubElement(shop,"url").text=settings.base_url
        SubElement(SubElement(shop,"currencies"),"currency",id="RUR",rate="1")
        SubElement(SubElement(shop,"categories"),"category",id="1").text="Промышленное оборудование"
        offers=SubElement(shop,"offers")
        for product in eligible:
            offer=SubElement(offers,"offer",id=product["sku"],available="true" if product.get("in_stock") is True else "false")
            cents=price_kopecks(product)
            for key,value in {"url":settings.base_url+"/models/"+product["slug"],"price":f"{cents//100}.{cents%100:02d}",
                              "currencyId":"RUR","categoryId":"1","name":product.get("name",product["slug"])}.items():
                SubElement(offer,key).text=value
            image=product.get("image","")
            if image.startswith("/static/"):
                SubElement(offer,"picture").text=settings.base_url+image
        return Response(tostring(tree,encoding="utf-8",xml_declaration=True),media_type="application/xml")

    return app


app = create_app()
