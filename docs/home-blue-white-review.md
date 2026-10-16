# Homepage blue/white revision — 2026-10-16

## Selected direction and scope

The user explicitly selected blue and white and asked to replace the crane/factory hero, prioritize seven named manufacturers, retain only Huadong among the previous Chinese references, remove pneumatic transport/calculation content and the blog, and keep oil. This revises the already selected site; there was no unresolved concept-choice boundary.

The homepage now has a white equipment hero, a blue heading and action, a text directory for Lutos, Robuschi, Kaeser, Atlas Copco, Kubicek, Busch and Pedro Gil, an AERZEN/Huadong equipment section, an oil section, and telephone/e-mail contacts. No services/workflow/blog/application sections remain in these homepage templates. Manufacturer names are text rather than invented logos. AERZEN's photograph has an explicit model caption; it is not presented as another manufacturer's product.

The corporate PNG has not arrived. The shared header/footer use a neutral textual company name, styled by `.brand-wordmark`; this is not a completed corporate-logo replacement.

## UI Pattern Forge evidence

The installed `ui-pattern-forge:compose-ui-patterns` skill, source registry, design-quality, design-system and motion-system guidance were read. No external UI package or runtime was installed.

1. **Local UI UX Pro Max:** full design-system query `industrial air blower manufacturer B2B blue white brand directory catalog`. Its luxury/glass recommendation was off-topic and was not adopted. One focused color retry, `industrial catalogue professional accessible blue white --domain color`, returned the B2B service palette principle: navy foreground, blue action, white/light surfaces. The final original tokens are in `static/css/blue-white.css`.
2. **Refero live pages, checked 2026-10-16:** [Custo detail](https://styles.refero.design/style/3ad131ed-b603-49a3-9491-7407db6cb423), original [custo.io](https://custo.io/), and [Teenage Engineering detail](https://styles.refero.design/style/aecf9dda-5cba-4dc7-9e73-59b65d895cdf), original [teenage.engineering](https://teenage.engineering/). Custo is the primary composition reference: one real piece of equipment, large plain typography, flat surfaces, space and thin dividers. The user-selected blue/white palette takes precedence over that reference's monochrome palette. The current style descriptions were inspected; no Refero screenshot, source code, font or other asset was imported. Refero is a research source, not a licensed component source.
3. **21st:** no `21st` MCP tool was exposed in the available tool inventory. [Official MCP page](https://21st.dev/mcp) was accessible; the previously considered [Interactive Gallery item](https://21st.dev/community/components/ruixen/interactive-gallery/default) returned a tool access error. Item code, dependencies and license could not be verified, so no component was imported. The implemented components are original Jinja/native HTML/CSS and retain the existing Python stack.

## Assets, access and license limits

- Hero: existing `/static/images/models/aerzen/delta-blower-open.png`, inspected as a real blue blower installation, 1000×1000. Source recorded by the existing photo manifest: [AERZEN Delta Blower](https://www.aerzen.com/us/products/product/blower-units-delta-blower-generation-5). Existing manufacturer's redistribution rights remain unconfirmed; this change does not establish a new commercial image license.
- Equipment section uses the existing sourced photo data and series captions. No image was synthesized, relabeled as another brand, or edited to remove a watermark.
- Oil: existing `/static/images/source/article-oil.webp`, inspected as Delta Lube 06 packaging, 1000×563; existing source [company oil article](https://vozduhoduvka-aerzen.ru/blog/oborudovanie-i-tehnologii/aerzen-delta-lube-otlichit-original/). This internal provenance link does not restore a blog section in the site's navigation.
- Existing system Arial/Helvetica font stack; no remote font, font license change, tracking, browser API or library dependency was added.

## Interface and motion

- Accent `#0755a5`, hover `#064483`, foreground `#17324d`, secondary text `#53687b`, white and pale blue surfaces, restrained 3px control radius.
- Primary actions have white text on blue; outlined actions keep blue text on white. The earlier `--yellow` token aliases the blue accent for compatibility, with explicit on-accent corrections for buttons/navigation.
- Hero equipment enters once with a 16px translation and opacity transition over 0.6s. It has no delay, loop, scroll interception or effect that blocks a control. On mobile the image follows the text and actions. Under `prefers-reduced-motion: reduce`, entrance and arrow movement are removed; natural scrolling and readable content remain.
- The brand directory is two columns on desktop, one on narrow screens. New full brand directories use three/two/one columns and series pages two/one columns. Product images retain dimensions and `object-fit: contain`.
- Contact actions are ordinary `tel:` and `mailto:` links. No new data collection was added and no disabled backend form was enabled.

## Changed files and checks

Owned changes: `templates/index.html`, `templates/_home_sections.html`, `static/css/home-hero.css`, `static/css/home-sections.css`, new `static/css/blue-white.css`, and this report. Shared route/data/export changes are handled separately by the integrating agent.

| Status | Check | Evidence |
| --- | --- | --- |
| готово | Homepage renders | FastAPI TestClient `GET /` returned HTTP 200 with seven `.home-brand-entry` links. |
| готово | Requested homepage content | No `factory-hall.jpg`, RSR, ERB, technical-blog or pneumatic-transport strings in the rendered homepage. Clear blower hero image present. |
| готово | Browser structure | Background IAB opened the updated local homepage and verified the seven brand links, AERZEN/Huadong, oil, direct contacts and photo caption in the accessibility tree. The separate temporary tab/server were then closed. |
| готово | Color contrast | WCAG luminance formula: white/blue primary action 7.36:1, main text/white 13.13:1, secondary text/white 5.78:1. |
| готово | Static motion and CSS checks | All three owned stylesheets have balanced braces and explicit reduced-motion rules; `git diff --check` passed. |
| не применимо | New runtime/dependency/transaction checks | No new package, account, payment or collection flow. Existing disabled workflows remain under the app's safeguards. |
| заблокировано | Corporate PNG replacement | Awaiting the file the user said they would send. Neutral company text remains meanwhile. |

Responsive screenshots, shared navigation behavior, final whole-app tests and public Pages verification are performed by the integrating agent after the content/route merge; the checks above do not claim that deployment is complete.
