"""Build a read-only viewing copy; Python backend/data are never exported."""
from __future__ import annotations
import argparse
import html
import json
import shutil
import sys
import tempfile
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from fastapi.testclient import TestClient
from app.config import Settings
from app.main import create_app


class PreviewHTML(HTMLParser):
    def __init__(self, site_url: str, route: str, cards: dict):
        super().__init__(convert_charrefs=False)
        self.site_url = site_url.rstrip('/')
        self.prefix = urlsplit(site_url).path.rstrip('/')
        self.route = route
        self.cards = cards
        self.out = []
        self.assets = set()
        self.skip = None
        self.forms = []

    def local_url(self, value):
        if not value.startswith('/') or value.startswith('//'):
            return value
        u = urlsplit(value)
        path = u.path
        if not path.startswith('/static/') and not path.endswith('/'):
            path += '/'
        return urlunsplit(('', '', self.prefix + path, u.query, u.fragment))

    def handle_decl(self, decl):
        self.out.append('<!' + decl + '>')

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'script' and a.get('type') == 'application/ld+json':
            self.skip = 'script'
            return
        if self.skip:
            return
        if tag == 'form':
            self.forms.append(a.get('method', 'get').lower() == 'post')
            if self.forms[-1]:
                a.pop('action', None)
                a.pop('method', None)
                a.pop('data-request-form', None)
                tag = 'div'
        if tag == 'input' and a.get('type') == 'hidden':
            return
        if self.forms and self.forms[-1] and tag in ('input', 'select', 'textarea', 'button'):
            a['disabled'] = None
            a.pop('name', None)
        a.pop('nonce', None)
        for key in ('href', 'src', 'action'):
            if key in a:
                source = a[key]
                if source.startswith('/static/'):
                    self.assets.add(urlsplit(source).path)
                a[key] = self.local_url(source)
        if tag == 'link' and a.get('rel') == 'canonical':
            a['href'] = self.site_url + (self.route + '/' if self.route != '/' else '/')
        if tag == 'meta' and a.get('property') == 'og:url':
            a['content'] = self.site_url + (self.route + '/' if self.route != '/' else '/')
        if tag == 'article' and a.get('id') in self.cards:
            a.update(self.cards[a['id']])
        self.out.append('<' + tag + ''.join(' ' + k + ('' if v is None else '="' + html.escape(str(v), quote=True) + '"') for k, v in a.items()) + '>')
        if tag == 'head':
            self.out.append('<meta name="robots" content="noindex,nofollow">')
        if tag == 'body':
            self.out.append('<noscript><p class="announcement">Демоверсия доступна без JavaScript. В каталоге показаны все модели; фильтры работают при включённом JavaScript.</p></noscript>')

    def handle_startendtag(self, tag, attrs):
        before = len(self.out)
        self.handle_starttag(tag, attrs)
        # SVG shapes must stay self-closing or later shapes become their children.
        void = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'}
        if tag not in void and len(self.out) > before:
            self.out[-1] = self.out[-1][:-1] + '/>'

    def handle_endtag(self, tag):
        if self.skip:
            if tag == self.skip:
                self.skip = None
            return
        if tag == 'form':
            if self.forms.pop():
                tag = 'div'
        if tag == 'body':
            src = self.prefix + '/static/js/public-preview.js'
            self.out.append('<script type="module" src="' + src + '"></script>')
        self.out.append('</' + tag + '>')

    def handle_data(self, data):
        if not self.skip:
            self.out.append(data)

    def handle_entityref(self, name):
        if not self.skip:
            self.out.append('&' + name + ';')

    def handle_charref(self, name):
        if not self.skip:
            self.out.append('&#' + name + ';')


def export(output: Path, site_url: str):
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise ValueError('Output directory must be empty')
    products = json.loads((ROOT / 'content/products.json').read_text())
    families = json.loads((ROOT / 'content/alternatives.json').read_text())
    articles = json.loads((ROOT / 'content/articles.json').read_text())
    routes = ['/', '/models', '/alternatives', '/solutions', '/repair', '/about', '/contact', '/articles',
              '/privacy', '/terms', '/cookies', '/payment', '/delivery']
    routes += ['/models/' + p['slug'] for p in products]
    routes += ['/alternatives/' + f['slug'] for f in families]
    routes += ['/articles/' + a['slug'] for a in articles]
    cards = {}
    for p in products:
        cards[p['slug']] = {
            'data-preview-kind': 'series' if p.get('is_series') else 'model',
            'data-preview-type': 'rotary' if 'Роторная' in p.get('type', '') else 'screw',
            'data-preview-search': ' '.join(str(p.get(k, '')) for k in ('brand', 'name', 'type', 'family')),
        }
    for family in families:
        for model in family['models']:
            cards[f"ref-{family['slug']}-{model['anchor']}"] = {
                'data-preview-kind': 'reference', 'data-preview-type': 'rotary',
                'data-preview-search': ' '.join((model['name'], family['name'], family['manufacturer'], family['technology'])),
            }
    assets = set()
    origin = urlunsplit((*urlsplit(site_url)[:2], '', '', ''))
    with tempfile.TemporaryDirectory(prefix='aerzen-export-data-') as data:
        settings = Settings(root_dir=ROOT, data_dir=Path(data), base_url=origin,
                            preview_mode=True, forms_enabled=False, commerce_enabled=False,
                            secure_cookies=False, allowed_hosts=('testserver',))
        with TestClient(create_app(settings)) as client:
            for route in routes:
                response = client.get(route)
                assert response.status_code == 200, route
                body = response.text.replace('Версия в разработке', 'Демоверсия для просмотра')
                body = body.replace('Необходимые cookies защищают формы и сохраняют корзину. Аналитика и рекламные сервисы не подключены.',
                                    'В демоверсии формы и корзина отключены. Аналитика и реклама не подключены. Выбор настроек сохраняется только в вашем браузере.')
                body = body.replace('Необходимые cookies защищают отправку форм и сохраняют состояние корзины. Они не используются для рекламного профилирования.',
                                    'Демонстрационная версия не отправляет формы и не использует корзину. Настройки сохраняются локально в браузере. Хостинг GitHub Pages ведёт технические журналы посещений для безопасности. Подробнее: <a href="https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement">конфиденциальность GitHub</a>.')
                if route == '/models':
                    marker = '<div class="product-grid">'
                    empty = '<div class="catalog-empty" data-preview-empty hidden><h2>Модели не найдены</h2><p>Измените запрос или сбросьте фильтры.</p><a class="button" href="/models">Все модели</a></div>'
                    body = body.replace(marker, marker + empty, 1)
                parser = PreviewHTML(site_url, route, cards)
                parser.feed(body)
                result = ''.join(parser.out)
                assert 'csrf_token' not in result and 'form_token' not in result and 'cart_token' not in result
                assert 'method="post"' not in result and 'action="/requests/' not in result
                target = output / route.lstrip('/') / 'index.html'
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(result)
                assets.update(parser.assets)
    for asset in assets:
        source = (ROOT / asset.lstrip('/')).resolve()
        assert source.is_relative_to(ROOT / 'static') and source.is_file(), asset
        target = output / asset.lstrip('/')
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    target = output / 'static/js/public-preview.js'
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / 'preview-assets/public-preview.js', target)
    (output / '.nojekyll').write_text('')
    (output / 'robots.txt').write_text('User-agent: *\nDisallow: /\n')
    (output / '404.html').write_text('<!doctype html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow"><title>Страница не найдена</title><h1>Страница не найдена</h1><a href="' + html.escape(site_url) + '/">На главную</a></html>')
    print(json.dumps({'output': str(output), 'pages': len(routes), 'assets': len(assets) + 1, 'backend_exported': False, 'forms_enabled': False, 'site_url': site_url}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--site-url', required=True)
    args = parser.parse_args()
    export(args.output.resolve(), args.site_url)
