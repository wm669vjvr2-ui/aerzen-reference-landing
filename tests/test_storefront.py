"""Regression checks for useful catalogue discovery and the independent storefront."""
from __future__ import annotations

import json
from urllib.parse import urlsplit

import pytest

from test_alternatives import PROJECT_ROOT, Page, make_site, schema_types


OWN_MODELS = {"delta-blower", "delta-hybrid", "delta-screw", "gm35s", "gm50l", "gm60s", "gm80l"}


class CatalogPage(Page):
    def __init__(self, text):
        self.product_ids = set()
        self.cards = []
        self.search_values = []
        self.sources = []
        self._card = None
        super().__init__(text)

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "article" and values.get("id"):
            self.product_ids.add(values["id"])
            self._card = {"id": values["id"], "kind": values.get("data-catalog-kind"),
                          "brand": values.get("data-catalog-brand"), "images": [], "links": []}
            self.cards.append(self._card)
        if self._card is not None:
            if tag == "img":
                self._card["images"].append(values)
            if tag == "a":
                self._card["links"].append(values.get("href", ""))
        if tag == "input" and values.get("name") == "q":
            self.search_values.append(values.get("value", ""))
        if values.get("src"):
            self.sources.append(values["src"])
        super().handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        if tag == "article":
            self._card = None
        super().handle_endtag(tag)


def reference_entries(app):
    brands = {"huadong-hdsr": "huadong", "mingtian-rsr": "mingtian", "erstvak-erb": "erstvak"}
    return [{"id": f"ref-{family['slug']}-{model['anchor']}", "brand": brands[family["slug"]],
             "url": f"/alternatives/{family['slug']}#{model['anchor']}", "model": model}
            for family in app.state.content.alternatives for model in family["models"]]


@pytest.fixture
def storefront(make_site):
    app, client, root = make_site()
    # The shared fixture includes a commerce-only test SKU; use the actual seven
    # catalogue entries here so their public discovery can be checked completely.
    path = root / "content/products.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    products = data["products"] if isinstance(data, dict) else data
    products[:] = [product for product in products if product["slug"] != "test-confirmed"]
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return app, client, root


def test_catalogue_contains_all_thirty_positions_with_reference_photos_first(storefront):
    app, client, _ = storefront
    response = client.get("/models")
    assert response.status_code == 200
    page = CatalogPage(response.text)
    references = reference_entries(app)
    assert len(references) == 23
    assert page.product_ids == OWN_MODELS | {entry["id"] for entry in references}
    assert len(page.cards) == 30
    assert [card["id"] for card in page.cards[:23]] == [entry["id"] for entry in references]
    assert {card["id"] for card in page.cards[23:]} == OWN_MODELS
    products = {product["slug"]: product for product in app.state.content.products}
    for index, card in enumerate(page.cards):
        assert card["images"], card["id"]
        photo = references[index]["model"]["photo"] if index < 23 else products[card["id"]]["photo"]
        assert card["images"][0]["src"] == photo["path"]
        assert card["images"][0]["alt"] == photo["alt"] and photo["alt"].strip()
        asset = PROJECT_ROOT / urlsplit(photo["path"]).path.lstrip("/")
        assert asset.is_file() and asset.stat().st_size > 1024, photo["path"]
        if index < 23:
            assert card["kind"] == "reference"
            assert card["brand"] == references[index]["brand"]
            assert references[index]["url"] in card["links"]
            assert all(not href.startswith(("/models/", "/cart", "/checkout")) for href in card["links"])
        else:
            assert card["kind"] == "aerzen" and card["brand"] == "aerzen"
    assert page.canonical == ["http://testserver/models"]
    assert not ({"Product", "Offer", "AggregateOffer"} & schema_types(page))


def test_own_models_keep_working_details_and_quote_routes(storefront):
    _, client, _ = storefront
    for slug in OWN_MODELS:
        detail = client.get("/models/" + slug)
        assert detail.status_code == 200
        page = Page(detail.text)
        assert len(page.headings) == 1
        quote = next(form for form in page.forms if form["action"] == "/requests/quote")
        assert quote["fields"]["product_slug"] == slug
        assert not any(form["action"] == "/cart/add" for form in page.forms)


@pytest.mark.parametrize("params, expected", [
    ({"type": "rotary"}, "all_rotary"),
    ({"type": "screw"}, {"delta-hybrid", "delta-screw"}),
    ({"kind": "series"}, {"delta-blower", "delta-hybrid", "delta-screw"}),
    ({"kind": "model"}, {"gm35s", "gm50l", "gm60s", "gm80l"}),
    ({"type": "rotary", "kind": "series"}, {"delta-blower"}),
    ({"type": "screw", "kind": "model"}, set()),
    ({"q": "  gM35s  "}, {"gm35s"}),
    ({"q": "dElTa", "type": "screw"}, {"delta-hybrid", "delta-screw"}),
    ({"kind": "reference"}, "all_references"),
    ({"brand": "huadong"}, "huadong"),
    ({"brand": "mingtian"}, "mingtian"),
    ({"brand": "erstvak"}, "erstvak"),
    ({"brand": "aerzen"}, OWN_MODELS),
    ({"brand": "huadong", "kind": "series"}, set()),
    ({"brand": "mingtian", "type": "screw"}, set()),
    ({"brand": "erstvak", "kind": "reference", "q": "ERB-100"}, "erb100"),
    ({"brand": "huadong", "q": "RSR"}, set()),
])
def test_catalogue_filters_and_case_insensitive_search(storefront, params, expected):
    app, client, _ = storefront
    references = reference_entries(app)
    if expected == "all_references":
        expected = {entry["id"] for entry in references}
    elif expected == "all_rotary":
        expected = {entry["id"] for entry in references} | {"delta-blower", "gm35s", "gm50l", "gm60s", "gm80l"}
    elif isinstance(expected, str):
        expected = {entry["id"] for entry in references if
                    (entry["model"]["name"] == "ERB-100" if expected == "erb100" else entry["brand"] == expected)}
    response = client.get("/models", params=params)
    assert response.status_code == 200
    page = CatalogPage(response.text)
    assert page.product_ids == expected
    assert page.canonical == ["http://testserver/models"]
    if "q" in params:
        assert page.search_values and all(value == params["q"].strip() for value in page.search_values)
    if not expected:
        assert "Модели не найдены" in " ".join(page.text)


@pytest.mark.parametrize("params", [
    {"q": "x" * 101}, {"type": "turbine"}, {"kind": "all"},
    {"type": "<script>"}, {"kind": "../models"},
    {"brand": "unknown"}, {"brand": "<script>"}, {"brand": "HUADONG"},
])
def test_catalogue_rejects_unsupported_parameters(storefront, params):
    _, client, _ = storefront
    assert client.get("/models", params=params).status_code == 422


def test_catalogue_query_is_escaped_and_empty_results_are_actionable(storefront):
    _, client, _ = storefront
    payload = '\"><script>alert("catalog-query")</script><input name="admin" value="yes">'
    response = client.get("/models", params={"q": payload})
    assert response.status_code == 200
    assert payload not in response.text
    page = CatalogPage(response.text)
    assert page.search_values and all(value == payload for value in page.search_values)
    assert not page.product_ids
    assert not any('alert("catalog-query")' in script for script in page.script_text)
    assert all("admin" not in form["fields"] for form in page.forms)
    assert "Модели не найдены" in " ".join(page.text)
    assert any(link["href"] == "/alternatives" for link in page.links)


@pytest.mark.parametrize("query, family_slug", [
    ("hDsR150", "huadong-hdsr"), ("rSr80", "mingtian-rsr"), ("ERB-100", "erstvak-erb"),
])
def test_reference_lookup_shows_model_photo_and_no_commerce(storefront, query, family_slug):
    app, client, _ = storefront
    response = client.get("/models", params={"q": query})
    assert response.status_code == 200
    page = CatalogPage(response.text)
    expected = next(entry for entry in reference_entries(app)
                    if entry["model"]["name"].casefold() == query.casefold())
    assert page.product_ids == {expected["id"]}
    assert len(page.cards) == 1 and page.cards[0]["kind"] == "reference"
    assert page.cards[0]["images"][0]["src"] == expected["model"]["photo"]["path"]
    assert any(link["href"] == expected["url"] for link in page.links)
    assert not ({"Product", "Offer", "AggregateOffer"} & schema_types(page))
    assert not any(form["action"].startswith(("/cart/", "/checkout")) for form in page.forms)
    assert client.get("/models/" + family_slug).status_code == 404
    missing = CatalogPage(client.get("/models", params={"q": "unknown-blower-model"}).text)
    assert not missing.cards


def test_homepage_uses_independent_structure_and_never_renders_legacy_paths(storefront):
    _, client, root = storefront
    path = root / "content/site.json"
    site = json.loads(path.read_text(encoding="utf-8"))
    site["paths"] = [{"title": "LEGACY_MAIN_SITE_ENTRY", "description": "legacy",
                      "href": "https://legacy-entry.example/", "image": "/static/images/source/legacy.webp"}]
    path.write_text(json.dumps(site, ensure_ascii=False), encoding="utf-8")
    response = client.get("/")
    assert response.status_code == 200
    assert "LEGACY_MAIN_SITE_ENTRY" not in response.text
    assert "legacy-entry.example" not in response.text
    assert "Знаю модель" not in response.text
    assert "Есть задача" not in response.text
    assert len(Page(response.text).headings) == 1


def test_public_routes_do_not_reintroduce_main_site_links_or_old_photos(storefront):
    app, client, _ = storefront
    paths = ["/", "/models", "/solutions", "/repair", "/about", "/contact", "/articles", "/alternatives"]
    paths += ["/models/" + slug for slug in OWN_MODELS]
    paths += ["/articles/" + item["slug"] for item in app.state.content.articles]
    paths += ["/alternatives/" + family["slug"] for family in app.state.content.alternatives]
    main_hostname = urlsplit(app.state.content.site["source_url"]).hostname
    for path in paths:
        response = client.get(path, follow_redirects=False)
        assert response.status_code == 200, path
        page = CatalogPage(response.text)
        assert all(urlsplit(link["href"]).hostname != main_hostname for link in page.links), path
        assert all(not source.startswith("/static/images/source/") for source in page.sources), path
        assert not response.history
