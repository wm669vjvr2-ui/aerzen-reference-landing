/* Read-only viewing copy: filters only; never submits data or stores enquiries. */
const form = document.querySelector('.catalog-filter');
const cards = [...document.querySelectorAll('[data-catalog-kind]')];
if (form && cards.length) {
  const fields = Object.fromEntries(['q','brand','type','kind'].map(name => [name, form.elements.namedItem(name)]));
  const empty = document.querySelector('[data-preview-empty]');
  const count = document.querySelector('.catalog-toolbar strong');
  // Read the catalogue's options so exported filters keep pace with its brands.
  const allowed = Object.fromEntries(['brand','type','kind'].map(key =>
    [key, [...fields[key].options].map(option => option.value)]));
  function apply() {
    const params = new URLSearchParams(location.search);
    fields.q.value = (params.get('q') || '').slice(0,100);
    for (const key of ['brand','type','kind']) fields[key].value = allowed[key].includes(params.get(key) || '') ? (params.get(key) || '') : '';
    const query = fields.q.value.trim().toLocaleLowerCase('ru');
    let visible = 0;
    for (const card of cards) {
      card.hidden = !((!fields.brand.value || fields.brand.value === card.dataset.catalogBrand)
        && (!fields.type.value || fields.type.value === card.dataset.previewType)
        && (!fields.kind.value || fields.kind.value === card.dataset.previewKind)
        && card.dataset.previewSearch.toLocaleLowerCase('ru').includes(query));
      if (!card.hidden) visible++;
    }
    count.textContent = String(visible);
    empty.hidden = visible > 0;
    const header = document.querySelector('#header-query');
    if (header) header.value = fields.q.value;
  }
  form.addEventListener('submit', event => {
    event.preventDefault();
    const params = new URLSearchParams();
    for (const key of ['q','brand','type','kind']) if (fields[key].value) params.set(key, fields[key].value);
    const query = params.toString();
    history.pushState(null,'',location.pathname + (query ? '?' + query : ''));
    apply();
  });
  addEventListener('popstate',apply);
  apply();
}
