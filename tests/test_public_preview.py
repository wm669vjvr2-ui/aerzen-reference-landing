"""The shared viewing copy must never export server state or live submission forms."""
from html.parser import HTMLParser
from urllib.parse import urlsplit, unquote

import pytest
from scripts.export_preview import export


class PublicPage(HTMLParser):
    def __init__(self, body):
        super().__init__()
        self.urls, self.ids, self.forms, self.cards = [], [], [], []
        self.feed(body)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if 'id' in attrs:
            self.ids.append(attrs['id'])
        if tag == 'form':
            self.forms.append(attrs)
        if tag == 'article' and 'data-catalog-kind' in attrs:
            self.cards.append(attrs)
        for key in ('href', 'src', 'action'):
            if key in attrs:
                self.urls.append(attrs[key])


@pytest.fixture(scope='module')
def public_export(tmp_path_factory):
    output = tmp_path_factory.mktemp('public-preview')
    export(output, 'https://wm669vjvr2-ui.github.io/aerzen-reference-landing')
    return output


def test_public_export_has_no_server_files_or_submission_tokens(public_export):
    assert not (public_export / 'app').exists()
    assert not (public_export / 'content').exists()
    assert not (public_export / 'cart').exists()
    assert not (public_export / 'checkout').exists()
    for path in public_export.rglob('*'):
        if path.is_file():
            assert path.suffix.lower() in {'.html', '.css', '.js', '.png', '.jpg', '.webp', '.svg', '.txt', ''}
        if path.suffix == '.html':
            body = path.read_text()
            assert all(token not in body for token in ('csrf_token', 'form_token', 'cart_token', 'data-request-form'))
            assert 'noindex,nofollow' in body
            assert all(form.get('method', 'get').lower() == 'get' for form in PublicPage(body).forms)


def test_all_public_paths_assets_and_fragments_resolve(public_export):
    pages = list(public_export.rglob('*.html'))
    assert len(pages) == 27
    prefix = '/aerzen-reference-landing/'
    for path in pages:
        page = PublicPage(path.read_text())
        assert len(page.ids) == len(set(page.ids))
        for link in page.urls:
            url = urlsplit(link)
            if url.scheme or url.netloc:
                continue
            if url.path:
                assert url.path.startswith(prefix), link
                target = public_export / unquote(url.path.removeprefix(prefix))
                if target.is_dir():
                    target = target / 'index.html'
            else:
                target = path
            assert target.is_file(), link
            if url.fragment and target.suffix == '.html':
                assert unquote(url.fragment) in PublicPage(target.read_text()).ids


def test_public_catalogue_preserves_thirty_cards_and_filter_metadata(public_export):
    page = PublicPage((public_export / 'models/index.html').read_text())
    assert len(page.cards) == 30
    assert sum(c['data-preview-kind'] == 'reference' for c in page.cards) == 23
    assert sum(c['data-preview-kind'] == 'series' for c in page.cards) == 3
    assert sum(c['data-preview-kind'] == 'model' for c in page.cards) == 4
    assert all(c.get('data-preview-search') and c.get('data-preview-type') for c in page.cards)
    assert all(c['data-catalog-kind'] == 'reference' for c in page.cards[:23])


def test_export_preserves_sibling_svg_shapes():
    from xml.etree import ElementTree
    from scripts.export_preview import PreviewHTML
    parser = PreviewHTML('https://example.test/preview', '/', {})
    parser.feed('<svg viewBox="0 0 24 24"><circle cx="10" cy="10" r="6"/><path d="m15 15 6 6"/></svg>')
    svg = ElementTree.fromstring(''.join(parser.out))
    assert [node.tag for node in svg] == ['circle', 'path']
    assert len(svg[0]) == 0
