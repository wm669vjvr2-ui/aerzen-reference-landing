from __future__ import annotations

import json
import re
import shutil
import os
import subprocess
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


@pytest.fixture
def setup(tmp_path):
    root = tmp_path / "site"
    (root / "content").mkdir(parents=True)
    (root / "templates").mkdir()
    site = {"name": "Test only", "legal": {"owner_confirmed": True, "privacy_ready": True,
            "privacy_contact": "test@example.test", "privacy_version": "test-v1", "commerce_terms_ready": True},
            "seller": {"confirmed": True, "legal_name": "TEST SELLER", "inn": "0000000000", "address": "TEST ADDRESS",
            "bank_name": "TEST BANK", "bank_bik": "000000000", "bank_account": "00000000000000000000",
            "correspondent_account": "00000000000000000000"}}
    products = [{"slug": "confirmed-sku", "sku": "TEST-01", "name": "Test product", "price_rub": "2000000.00",
                 "price_confirmed": True, "sku_confirmed": True, "purchasable": True, "in_stock": True,
                 "image": "/static/test.webp"}, {"slug": "unknown-price", "sku": "UNCONFIRMED", "name": "Family",
                 "price_rub": None, "source_price": 1000000, "purchasable": False}]
    (root / "content/site.json").write_text(json.dumps(site))
    (root / "content/products.json").write_text(json.dumps(products))
    tpl = '<!doctype html><html><form><input name="csrf_token" value="{{ csrf_token }}"><input name="form_token" value="{{ form_token }}"><input name="cart_token" value="{{ cart_token }}"></form>{{ title }}{{ message }}{% if order %}{{ order.status }}{% endif %}</html>'
    for name in ("index", "models", "product", "solutions", "repair", "about", "contact", "articles", "article",
                 "legal", "error", "request_received", "cart", "checkout", "order", "invoice"):
        (root / "templates" / (name + ".html")).write_text(tpl)
    settings = Settings(root_dir=root, data_dir=tmp_path / "private", secret_key="test-key-"+"0"*40,
                        preview_mode=True, forms_enabled=True, commerce_enabled=True, secure_cookies=False)
    app = create_app(settings)
    with TestClient(app) as client:
        yield app, client, root


def fields_from(response, purpose="lead"):
    values = dict(re.findall(r'name="([^\"]+)" value="([^\"]+)"', response.text))
    if purpose == "cart":
        values["form_token"] = values.pop("cart_token")
    else:
        values.pop("cart_token", None)
    return values


def lead_form(client):
    return {**fields_from(client.get("/solutions")), "name": "Test Person", "company": "Test",
            "email": "test@example.test", "phone": "", "message": "Test message", "consent": "on", "website": ""}


def count(app, table):
    with app.state.store.connect() as db:
        return db.execute("SELECT COUNT(*) FROM " + table).fetchone()[0]


def test_csrf_origin_allowed_fields_and_consent(setup):
    app, client, _ = setup
    form = lead_form(client)
    assert client.post("/requests/task", data={**form, "csrf_token": "forged"}).status_code == 403
    assert client.post("/requests/task", data=form, headers={"origin": "https://evil.example"}).status_code == 403
    assert client.post("/requests/task", data={**form, "status": "paid"}).status_code == 400
    assert client.post("/requests/task", data={**form, "consent": ""}).status_code == 422
    assert count(app, "leads") == 0


def test_lead_idempotency_and_changed_payload(setup):
    app, client, _ = setup
    form = lead_form(client)
    assert client.post("/requests/task", data=form).status_code == 200
    assert client.post("/requests/task", data=form).status_code == 200
    assert count(app, "leads") == 1
    assert client.post("/requests/task", data={**form, "message": "Different"}).status_code == 409
    with app.state.store.connect() as db:
        lead = db.execute("SELECT * FROM leads").fetchone()
        assert lead["policy_version"] == "test-v1"
        assert lead["consent_at"] > 0


def test_parallel_duplicate_has_one_row(setup):
    app, client, _ = setup
    form = lead_form(client)
    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(pool.map(lambda _: client.post("/requests/task", data=form).status_code, range(2)))
    assert statuses == [200, 200]
    assert count(app, "leads") == 1


def test_rate_honeypot_and_size(setup):
    app, client, _ = setup
    assert client.post("/requests/task", data={**lead_form(client), "website": "spam"}).status_code == 200
    assert count(app, "leads") == 0
    assert client.post("/requests/task", content=b"x"*21000, headers={"Content-Type": "application/x-www-form-urlencoded"}).status_code == 413
    for i in range(7):
        assert client.post("/requests/task", data={**lead_form(client), "message": str(i)}).status_code == 200
    assert client.post("/requests/task", data=lead_form(client)).status_code == 429


def test_unverified_price_cannot_be_purchased_and_price_field_rejected(setup):
    app, client, _ = setup
    fields = fields_from(client.get("/models/unknown-price"), "cart")
    assert client.post("/cart/add", data={**fields, "slug": "unknown-price", "quantity": "1"}).status_code == 422
    assert client.post("/cart/add", data={**fields, "slug": "confirmed-sku", "price_rub": "1"}).status_code == 400
    assert count(app, "orders") == 0


def order_form(client):
    fields = fields_from(client.get("/models/confirmed-sku"), "cart")
    assert client.post("/cart/add", data={**fields, "slug": "confirmed-sku", "quantity": "1"}).status_code == 200
    return {**fields_from(client.get("/checkout")), "name": "Test Person", "company": "Test",
            "email": "test@example.test", "phone": "", "message": "", "inn": "0000000000", "delivery_address": "Test address",
            "consent": "on", "website": ""}


def test_order_price_ownership_idempotency_and_paid_return(setup):
    app, client, _ = setup
    form = order_form(client)
    result = client.post("/checkout", data=form, follow_redirects=False)
    assert result.status_code == 303
    path = result.headers["location"]
    assert client.post("/checkout", data=form, follow_redirects=False).headers["location"] == path
    assert count(app, "orders") == 1
    assert client.get(path+"?status=paid").status_code == 200
    assert "awaiting_payment" in client.get(path).text
    with TestClient(app) as other:
        assert other.get(path).status_code == 404
        assert other.get(path+"/invoice").status_code == 404
    assert client.get("/orders/00000000000000000000000000000000").status_code == 404
    assert client.get(path+"/invoice").status_code == 200
    with app.state.store.connect() as db:
        row = db.execute("SELECT * FROM orders").fetchone()
        assert row["total_kopecks"] == 200000000
        assert row["status"] == "awaiting_payment"


def test_price_changes_require_recheckout(setup):
    app, client, root = setup
    form = order_form(client)
    products = json.loads((root / "content/products.json").read_text())
    products[0]["price_rub"] = "2500000"
    (root / "content/products.json").write_text(json.dumps(products))
    assert client.post("/checkout", data=form).status_code == 409
    assert count(app, "orders") == 0


def test_feed_and_business_readiness(setup):
    app, client, root = setup
    response = client.get("/feed.xml")
    assert response.status_code == 200
    assert "2000000.00" in response.text
    assert "unknown-price" not in response.text
    site = json.loads((root / "content/site.json").read_text())
    site["legal"]["owner_confirmed"] = False
    (root / "content/site.json").write_text(json.dumps(site))
    assert client.get("/feed.xml").status_code == 503
    assert client.post("/requests/task", data=lead_form(client)).status_code == 503


def test_headers_service_paths_and_private_storage(setup):
    app, client, _ = setup
    response = client.get("/")
    assert response.status_code == 200
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    assert "httponly" in response.headers["set-cookie"].lower()
    assert client.get("/docs").status_code == 404
    assert client.get("/.env").status_code == 404
    assert client.get("/static/../app/config.py").status_code == 404
    assert "Disallow: /" in client.get("/robots.txt").text
    assert client.get("/checkout").headers["cache-control"] == "no-store"
    assert client.get("/orders/invalid").status_code == 404


def test_real_commerce_templates_and_consent_value(setup):
    app, client, root = setup
    shutil.copytree(Path(__file__).resolve().parents[1]/"templates",root/"templates",dirs_exist_ok=True)
    product=client.get("/models/confirmed-sku")
    assert product.status_code == 200
    # The product's real buy form uses a cart-purpose token; its quote form uses a lead token.
    cart_form=re.search(r'<form action="/cart/add".*?</form>',product.text,re.S).group(0)
    fields=dict(re.findall(r'name="([^\"]+)" value="([^\"]+)"',cart_form))
    assert client.post("/cart/add",data=fields).status_code == 200
    checkout=client.get("/checkout")
    values=dict(re.findall(r'name="(csrf_token|form_token)" value="([^\"]+)"',checkout.text))
    response=client.post("/checkout",data={**values,"name":"Test Person","company":"Test","email":"test@example.test",
                       "phone":"+79990000000","message":"","inn":"0000000000","delivery_address":"Test address","consent":"yes","website":""},
                       follow_redirects=False)
    assert response.status_code == 303
    path=response.headers["location"]
    assert f'href="{path}/invoice"' in client.get(path).text
    invoice=client.get(path+"/invoice")
    assert invoice.status_code == 200
    assert "Test product" in invoice.text
    assert "2 000 000" in invoice.text


def test_operator_export_and_deletion_are_local_and_private(setup, tmp_path):
    app, client, _ = setup
    assert client.post("/requests/task",data=lead_form(client)).status_code == 200
    with app.state.store.connect() as db:
        record_id=db.execute("SELECT id FROM leads").fetchone()[0]
    task_env={**os.environ,"AERZEN_DATA_DIR":str(app.state.settings.data_dir),"AERZEN_PREVIEW_MODE":"true"}
    output=tmp_path/"private-export.json"
    result=subprocess.run([sys.executable,"-m","app.manage","export",record_id,"--output",str(output)],
                          env=task_env,capture_output=True,text=True)
    assert result.returncode == 0
    assert output.stat().st_mode & 0o777 == 0o600
    assert json.loads(output.read_text())["leads"][0]["id"] == record_id
    assert "test@example.test" not in result.stdout
    deletion=subprocess.run([sys.executable,"-m","app.manage","delete",record_id,"--confirm"],env=task_env,capture_output=True,text=True)
    assert deletion.returncode == 0
    assert count(app,"leads") == 0
    assert client.get("/admin").status_code == 404
