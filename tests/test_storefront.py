"""Regression checks for useful catalogue discovery and the independent storefront."""
from __future__ import annotations

import json
from urllib.parse import urlsplit

import pytest

from test_alternatives import PROJECT_ROOT, Page, make_site, schema_types


OWN_MODELS = {"delta-blower", "delta-hybrid", "delta-screw", "gm35s", "gm50l", "gm60s", "gm80l"}
BRAND_SLUGS = {"lutos", "robuschi", "kaeser", "atlas-copco", "kubicek", "busch", "pedro-gil"}


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
    return [{"id": f"ref-{family['slug']}-{model['anchor']}", "brand": family["slug"].split("-")[0],
             "url": f"/alternatives/{family['slug']}#{model['anchor']}", "model": model}
            for family in app.state.content.alternatives for model in family["models"]]


def brand_entries(app):
    return [{"id": f"brand-{brand['slug']}-{series['slug']}", "brand": brand["slug"], "series": series,
             "url": f"/brands/{brand['slug']}#{series['slug']}"}
            for brand in app.state.content.brands for series in brand["series"]]


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


def test_catalogue_contains_known_brands_aerzen_and_huadong(storefront):
    app, client, _ = storefront
    response = client.get("/models")
    assert response.status_code == 200
    page = CatalogPage(response.text)
    references = reference_entries(app)
    assert len(references) == 11
    brands = brand_entries(app)
    assert {entry["brand"] for entry in brands} == BRAND_SLUGS
    assert page.product_ids == OWN_MODELS | {entry["id"] for entry in references + brands}
    assert len(page.cards) == 18 + len(brands)
    products = {product["slug"]: product for product in app.state.content.products}
    references_by_id = {entry["id"]: entry for entry in references}
    brands_by_id = {entry["id"]: entry for entry in brands}
    for card in page.cards:
        if card["id"] in references_by_id:
            reference = references_by_id[card["id"]]
            photo = reference["model"]["photo"]
            assert card["kind"] == "reference"
            assert card["brand"] == reference["brand"] == "huadong"
            assert reference["url"] in card["links"]
            assert all(not href.startswith(("/models/", "/cart", "/checkout")) for href in card["links"])
        elif card["id"] in products:
            photo = products[card["id"]]["photo"]
            assert card["kind"] == "aerzen" and card["brand"] == "aerzen"
        else:
            entry = brands_by_id[card["id"]]
            photo = entry["series"].get("photo")
            assert card["kind"] == "brand-series" and card["brand"] == entry["brand"]
            assert entry["url"] in card["links"]
            assert all(not href.startswith(("/cart", "/checkout")) for href in card["links"])
        if photo:
            assert card["images"], card["id"]
            assert card["images"][0]["src"] == photo["path"]
            assert card["images"][0]["alt"] == photo["alt"] and photo["alt"].strip()
        for image in card["images"]:
            asset = PROJECT_ROOT / urlsplit(image["src"]).path.lstrip("/")
            assert asset.is_file() and asset.stat().st_size > 1024, image["src"]
            assert image.get("alt", "").strip()
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
    ({"type": "screw"}, "all_screw"),
    ({"type": "turbo"}, "all_turbo"),
    ({"kind": "series"}, "all_series"),
    ({"kind": "model"}, {"gm35s", "gm50l", "gm60s", "gm80l"}),
    ({"type": "screw", "kind": "model"}, set()),
    ({"q": "  gM35s  "}, {"gm35s"}),
    ({"q": "SD28"}, {"brand-kubicek-screw-sd"}),
    ({"q": "dElTa", "type": "screw"}, {"delta-hybrid", "delta-screw"}),
    ({"kind": "reference"}, "all_references"),
    ({"brand": "huadong"}, "huadong"),
    ({"brand": "robuschi", "q": "Robushi"}, "robuschi"),
    ({"brand": "aerzen"}, OWN_MODELS),
    ({"brand": "huadong", "kind": "series"}, set()),
    ({"brand": "robuschi", "kind": "reference"}, set()),
    ({"brand": "huadong", "q": "RSR"}, set()),
])
def test_catalogue_filters_and_case_insensitive_search(storefront, params, expected):
    app, client, _ = storefront
    references = reference_entries(app)
    brands = brand_entries(app)
    if expected == "all_references":
        expected = {entry["id"] for entry in references}
    elif expected == "all_rotary":
        expected = ({entry["id"] for entry in references}
                    | {"delta-blower", "gm35s", "gm50l", "gm60s", "gm80l"}
                    | {entry["id"] for entry in brands if entry["series"]["type"] == "rotary"})
    elif expected == "all_screw":
        expected = {"delta-hybrid", "delta-screw"} | {entry["id"] for entry in brands if entry["series"]["type"] == "screw"}
    elif expected == "all_turbo":
        expected = {entry["id"] for entry in brands if entry["series"]["type"] == "turbo"}
    elif expected == "all_series":
        expected = {"delta-blower", "delta-hybrid", "delta-screw"} | {entry["id"] for entry in brands}
    elif isinstance(expected, str):
        expected = {entry["id"] for entry in references + brands if entry["brand"] == expected}
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
    {"brand": "mingtian"}, {"brand": "erstvak"},
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
    assert any(link["href"] == "/models" for link in page.links)


@pytest.mark.parametrize("query, family_slug", [
    ("hDsR150", "huadong-hdsr"),
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
    page = Page(response.text)
    assert len(page.headings) == 1
    visible = " ".join(page.text).casefold()
    assert all(removed not in visible for removed in ("пневмотранспорт", "расчёт", "расчет", "блог"))
    assert "/static/images/storefront/factory-hall.jpg" not in response.text


def test_each_requested_brand_has_distinct_page_source_and_catalogue_filter(storefront):
    app, client, _ = storefront
    assert {brand["slug"] for brand in app.state.content.brands} == BRAND_SLUGS
    directory = Page(client.get("/brands").text)
    assert len(directory.headings) == 1
    for brand in app.state.content.brands:
        path = "/brands/" + brand["slug"]
        assert any(link["href"] == path for link in directory.links)
        response = client.get(path, follow_redirects=False)
        assert response.status_code == 200 and not response.history
        page = Page(response.text)
        assert len(page.headings) == 1 and brand["name"] in page.headings[0]
        assert page.canonical == ["http://testserver" + path]
        assert any(link["href"] == brand["source_url"] for link in page.links)
        assert not ({"Product", "Offer", "AggregateOffer"} & schema_types(page))
        assert not any(form["action"].startswith(("/cart/", "/checkout")) for form in page.forms)
        catalogue = CatalogPage(client.get("/models", params={"brand": brand["slug"]}).text)
        assert catalogue.product_ids == {entry["id"] for entry in brand_entries(app) if entry["brand"] == brand["slug"]}
        assert catalogue.cards and all(card["brand"] == brand["slug"] for card in catalogue.cards)
    assert client.get("/brands/unknown-brand").status_code == 404


def test_removed_blog_services_and_other_chinese_families_are_not_routes(storefront):
    app, client, _ = storefront
    removed = ["/articles", "/solutions", "/repair", "/alternatives/mingtian-rsr", "/alternatives/erstvak-erb"]
    removed += ["/articles/" + article["slug"] for article in app.state.content.articles]
    for path in removed:
        assert client.get(path, follow_redirects=False).status_code == 404, path
    assert client.get("/oil").status_code == 200


def test_public_routes_do_not_reintroduce_main_site_links_or_old_photos(storefront):
    app, client, _ = storefront
    paths = ["/", "/models", "/brands", "/oil", "/about", "/contact", "/alternatives"]
    paths += ["/models/" + slug for slug in OWN_MODELS]
    paths += ["/brands/" + item["slug"] for item in app.state.content.brands]
    paths += ["/alternatives/" + family["slug"] for family in app.state.content.alternatives]
    main_hostname = urlsplit(app.state.content.site["source_url"]).hostname
    for path in paths:
        response = client.get(path, follow_redirects=False)
        assert response.status_code == 200, path
        page = CatalogPage(response.text)
        assert all(urlsplit(link["href"]).hostname != main_hostname for link in page.links), path
        assert all(not source.startswith("/static/images/source/") or source == "/static/images/source/article-oil.webp"
                   for source in page.sources), path
        assert not response.history
