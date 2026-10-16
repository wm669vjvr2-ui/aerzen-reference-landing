from __future__ import annotations

import json
import shutil
from decimal import Decimal
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit
from xml.etree import ElementTree

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FAMILY_COUNTS = {"huadong-hdsr": 11}
DISCLAIMER = "Эти модели не поставляем."


class Page(HTMLParser):
    """Parse the rendered contract without depending on frontend class names."""

    def __init__(self, text: str):
        super().__init__(convert_charrefs=True)
        self.headings: list[str] = []
        self.canonical: list[str] = []
        self.refreshes: list[str] = []
        self.forms: list[dict] = []
        self.links: list[dict] = []
        self.text: list[str] = []
        self.script_text: list[str] = []
        self._heading: list[str] | None = None
        self._form: dict | None = None
        self._textarea: dict | None = None
        self._in_script = False
        self._link: dict | None = None
        self.feed(text)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]):
        values = dict(attrs)
        if tag == "h1":
            self._heading = []
        if tag == "link" and "canonical" in (values.get("rel") or "").split():
            self.canonical.append(values.get("href") or "")
        if tag == "meta" and (values.get("http-equiv") or "").lower() == "refresh":
            self.refreshes.append(values.get("content") or "")
        if tag == "form":
            self._form = {"action": values.get("action", ""), "fields": {}, "textareas": {}}
            self.forms.append(self._form)
        if tag == "input" and self._form is not None and values.get("name"):
            self._form["fields"][values["name"]] = values.get("value") or ""
        if tag == "textarea" and self._form is not None:
            self._textarea = {"name": values.get("name"), "parts": []}
        if tag == "script":
            self._in_script = True
        if tag == "a":
            self._link = {"href": values.get("href", ""), "parts": []}

    def handle_data(self, text: str):
        self.text.append(text)
        if self._heading is not None:
            self._heading.append(text)
        if self._textarea is not None:
            self._textarea["parts"].append(text)
        if self._in_script:
            self.script_text.append(text)
        if self._link is not None:
            self._link["parts"].append(text)

    def handle_endtag(self, tag: str):
        if tag == "h1" and self._heading is not None:
            self.headings.append(" ".join("".join(self._heading).split()))
            self._heading = None
        if tag == "textarea" and self._textarea is not None:
            value = "".join(self._textarea["parts"])
            self._form["textareas"][self._textarea["name"]] = value
            self._textarea = None
        if tag == "form":
            self._form = None
        if tag == "script":
            self._in_script = False
        if tag == "a" and self._link is not None:
            self._link["text"] = " ".join("".join(self._link.pop("parts")).split())
            self.links.append(self._link)
            self._link = None


def schema_types(document: Page) -> set[str]:
    result: set[str] = set()

    def visit(value):
        if isinstance(value, dict):
            kind = value.get("@type", [])
            result.update([kind] if isinstance(kind, str) else kind)
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    for script in document.script_text:
        try:
            visit(json.loads(script))
        except (ValueError, TypeError):
            continue
    return result


@pytest.fixture
def make_site(tmp_path):
    """Use real content/templates and test-only legal/SKU data in private storage."""
    clients = []

    def build(*, preview_mode=True):
        root = tmp_path / f"site-{len(clients)}"
        root.mkdir()
        shutil.copytree(PROJECT_ROOT / "content", root / "content")
        shutil.copytree(PROJECT_ROOT / "templates", root / "templates")
        site_path = root / "content/site.json"
        site = json.loads(site_path.read_text(encoding="utf-8"))
        site["legal"].update({"owner_confirmed": True, "privacy_ready": True,
                              "privacy_contact": "operator@example.test", "privacy_version": "test-v1",
                              "commerce_terms_ready": True})
        site["seller"] = {"confirmed": True, "legal_name": "TEST SELLER", "inn": "0000000000",
                          "address": "TEST ADDRESS", "bank_name": "TEST BANK", "bank_bik": "000000000",
                          "bank_account": "00000000000000000000",
                          "correspondent_account": "00000000000000000000"}
        site_path.write_text(json.dumps(site, ensure_ascii=False), encoding="utf-8")
        products_path = root / "content/products.json"
        products = json.loads(products_path.read_text(encoding="utf-8"))
        if isinstance(products, dict):
            products = products["products"]
        confirmed = dict(products[-1])
        confirmed.update({"slug": "test-confirmed", "sku": "TEST-ALT-01", "name": "Test-only blower",
                          "price_rub": "1000.00", "price_confirmed": True, "sku_confirmed": True,
                          "purchasable": True, "in_stock": True})
        products.append(confirmed)
        products_path.write_text(json.dumps(products, ensure_ascii=False), encoding="utf-8")
        origin = "http://testserver" if preview_mode else "https://testserver"
        settings = Settings(root_dir=root, data_dir=tmp_path / f"private-{len(clients)}",
                            secret_key="test-alternatives-" + "0" * 40, preview_mode=preview_mode,
                            forms_enabled=True, commerce_enabled=True, secure_cookies=not preview_mode,
                            base_url=origin, allowed_hosts=("testserver",))
        app = create_app(settings)
        client = TestClient(app, base_url=origin)
        clients.append(client)
        return app, client, root

    yield build
    for client in clients:
        client.close()


def test_reference_pages_explain_comparison_context_and_are_distinct(make_site):
    app, client, _ = make_site()
    families = {item["slug"]: item for item in app.state.content.alternatives}
    assert set(FAMILY_COUNTS) == set(families)
    headings = []
    for path in ["/alternatives"] + ["/alternatives/" + slug for slug in FAMILY_COUNTS]:
        response = client.get(path, follow_redirects=False)
        assert response.status_code == 200
        assert not response.history
        page = Page(response.text)
        visible_text = " ".join(page.text)
        assert DISCLAIMER not in visible_text
        assert "справоч" in visible_text.casefold()
        assert "сравнен" in visible_text.casefold()
        assert len(page.headings) == 1 and page.headings[0]
        headings.extend(page.headings)
        assert page.canonical == ["http://testserver" + path]
        assert not page.refreshes
        main_hostname = urlsplit(app.state.content.site["source_url"]).hostname
        assert all(urlsplit(link["href"]).hostname != main_hostname for link in page.links)
        request_form = next(form for form in page.forms if form["action"].startswith("/requests/"))
        assert request_form["fields"]["product_slug"] == ""
        assert not ({"Product", "Offer", "AggregateOffer"} & schema_types(page))
        assert not any("location.replace" in script or "location.assign" in script for script in page.script_text)
    assert len(set(headings)) == len(headings)
    for slug, model_count in FAMILY_COUNTS.items():
        assert families[slug]["supply_status"] == "not_supplied"
        assert len(families[slug]["models"]) == model_count
    assert client.get("/alternatives/not-a-reference-model").status_code == 404


def test_reference_families_are_excluded_from_products_cart_and_feed(make_site):
    app, client, _ = make_site()
    content = app.state.content
    product_slugs = {product["slug"] for product in content.products}
    assert not (set(FAMILY_COUNTS) & product_slugs)
    reference_ids = {f"ref-{family['slug']}-{model['anchor']}"
                     for family in content.alternatives for model in family["models"]}
    reference_models = {model["anchor"] for family in content.alternatives for model in family["models"]}
    brand_slugs = {brand["slug"] for brand in content.brands}
    brand_series_ids = {f"brand-{brand['slug']}-{series['slug']}"
                        for brand in content.brands for series in brand["series"]}
    assert not ((reference_ids | reference_models | brand_slugs | brand_series_ids) & product_slugs)
    for slug in FAMILY_COUNTS:
        assert content.product(slug) is None
        assert content.alternative(slug) is not None
    confirmed_page = Page(client.get("/models/test-confirmed").text)
    cart_form = next(form for form in confirmed_page.forms if form["action"] == "/cart/add")
    for slug in set(FAMILY_COUNTS) | reference_ids | reference_models | brand_slugs | brand_series_ids:
        response = client.post("/cart/add", data={**cart_form["fields"], "slug": slug, "quantity": "1"})
        assert response.status_code == 422
    # Confirm the preceding rejections were not caused by disabled commerce or an invalid token.
    assert client.post("/cart/add", data=cart_form["fields"]).status_code == 200
    cart_response = client.get("/cart")
    assert cart_response.status_code == 200
    assert "Test-only blower" in cart_response.text
    feed_response = client.get("/feed.xml")
    assert feed_response.status_code == 200
    feed = ElementTree.fromstring(feed_response.content)
    assert [offer.attrib["id"] for offer in feed.findall("./shop/offers/offer")] == ["TEST-ALT-01"]
    for family in content.alternatives:
        assert family["slug"] not in feed_response.text
        assert family["slug"] not in cart_response.text
        assert family["name"] not in feed_response.text
    for brand in content.brands:
        assert brand["name"] not in feed_response.text


def test_reference_form_requests_an_alternative_without_fake_product(make_site):
    app, client, _ = make_site()
    family = app.state.content.alternative("huadong-hdsr")
    page = Page(client.get("/alternatives/huadong-hdsr").text)
    form = next(form for form in page.forms if form["action"].startswith("/requests/"))
    assert form["fields"]["product_slug"] == ""
    message = form["textareas"]["message"]
    assert family["name"] in message
    response = client.post(form["action"], data={**form["fields"], "name": "Test Person",
                           "company": "TEST", "email": "person@example.test", "phone": "",
                           "message": message, "consent": "yes", "website": ""})
    assert response.status_code == 200
    with app.state.store.connect() as db:
        leads = db.execute("SELECT payload FROM leads").fetchall()
    assert len(leads) == 1
    payload = json.loads(leads[0]["payload"])
    assert payload["product_slug"] == ""
    assert payload["message"] == message.strip()


@pytest.mark.parametrize("candidate_group", ["reference-and-brands", "brand-series"])
def test_reference_models_and_other_brands_cannot_become_quote_products(make_site, candidate_group):
    app, client, _ = make_site()
    family = app.state.content.alternative("huadong-hdsr")
    model = family["models"][0]
    page = Page(client.get("/alternatives/huadong-hdsr").text)
    form = next(form for form in page.forms if form["action"].startswith("/requests/"))
    if candidate_group == "reference-and-brands":
        candidates = {f"ref-{family['slug']}-{model['anchor']}"}
        candidates.update(brand["slug"] for brand in app.state.content.brands)
    else:
        candidates = {f"brand-{brand['slug']}-{brand['series'][0]['slug']}" for brand in app.state.content.brands}
    for candidate in candidates:
        response = client.post(form["action"], data={**form["fields"], "product_slug": candidate,
                               "name": "Test Person", "company": "TEST", "email": "person@example.test",
                               "phone": "", "message": "Compare the reference model", "consent": "yes", "website": ""})
        assert response.status_code == 422, candidate
    with app.state.store.connect() as db:
        assert db.execute("SELECT COUNT(*) FROM leads").fetchone()[0] == 0


def test_model_name_prefill_cannot_close_textarea_or_create_script(make_site):
    app, client, root = make_site()
    path = root / "content/alternatives.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    families = data["alternatives"] if isinstance(data, dict) else data
    payload = '</textarea><script>alert("reference-name")</script>'
    next(family for family in families if family["slug"] == "huadong-hdsr")["name"] = payload
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    response = client.get("/alternatives/huadong-hdsr")
    assert response.status_code == 200
    assert payload not in response.text
    page = Page(response.text)
    form = next(form for form in page.forms if form["action"].startswith("/requests/"))
    assert payload in form["textareas"]["message"]
    assert not any('alert("reference-name")' in script for script in page.script_text)


def test_huadong_unit_conversions_preserve_manufacturer_ranges(make_site):
    app, client, _ = make_site()
    families = {family["slug"]: family for family in app.state.content.alternatives}
    for slug, family in families.items():
        native_unit = "m3/min"
        multiplier = Decimal(60)
        for model in family["models"]:
            assert model["flow_source_unit"] == native_unit
            expected = [Decimal(str(value)) * multiplier for value in model["flow_native"]]
            assert [Decimal(str(value)) for value in model["flow_m3_h"]] == expected
            rendered = [Decimal(value.replace(",", ".")) for value in model["flow_display"].split("–")]
            assert rendered == expected
    hdsr = {model["name"]: model for model in families["huadong-hdsr"]["models"]}
    assert hdsr["HDSR150"]["pressure_display"] == "9,8–58,8"
    assert all(model["photo"]["scope"] == "series" for model in hdsr.values())


@pytest.mark.parametrize("preview_mode", [True, False])
def test_reference_sitemap_respects_preview_indexing(make_site, preview_mode):
    app, client, _ = make_site(preview_mode=preview_mode)
    sitemap = client.get("/sitemap.xml")
    assert sitemap.status_code == 200
    tree = ElementTree.fromstring(sitemap.content)
    locations = {element.text for element in tree.findall(".//{http://www.sitemaps.org/schemas/sitemap/0.9}loc")}
    page = client.get("/alternatives/huadong-hdsr")
    assert page.status_code == 200
    if preview_mode:
        assert not locations
        assert page.headers["x-robots-tag"] == "noindex, nofollow"
    else:
        expected = {"https://testserver/alternatives"}
        expected.update("https://testserver/alternatives/" + slug for slug in FAMILY_COUNTS)
        expected.update("https://testserver/brands/" + brand["slug"] for brand in app.state.content.brands)
        expected.update({"https://testserver/brands", "https://testserver/oil"})
        assert expected.issubset(locations)
        assert not any(path in location for location in locations for path in ("/articles", "/solutions", "/repair", "mingtian", "erstvak"))
        assert "noindex" not in page.headers.get("x-robots-tag", "")
