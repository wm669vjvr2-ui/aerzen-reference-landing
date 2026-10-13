/* Small progressive enhancements. All main navigation also works without JS. */
const dialogs = [...document.querySelectorAll('dialog')];
document.querySelectorAll('.mobile-menu nav a').forEach(link => link.addEventListener('click', () => link.closest('details').removeAttribute('open')));
let previousFocus = null;
function openDialog(dialog) {
  if (!dialog || !('showModal' in dialog)) return;
  previousFocus = document.activeElement;
  dialog.showModal();
  const field = dialog.querySelector('input:not([type=hidden])');
  (field || dialog.querySelector('button'))?.focus();
}
document.querySelectorAll('[data-close-dialog]').forEach(button => button.addEventListener('click', () => button.closest('dialog').close()));
dialogs.forEach(dialog => {
  dialog.addEventListener('keydown', event => { if (event.key === 'Escape') { event.preventDefault(); dialog.close(); } });
  dialog.addEventListener('close', () => previousFocus?.focus());
  dialog.addEventListener('click', event => { if (event.target === dialog) { const r=dialog.getBoundingClientRect(); if(event.clientX<r.left||event.clientX>r.right||event.clientY<r.top||event.clientY>r.bottom)dialog.close(); } });
});
const searchDialog=document.querySelector('[data-search-dialog]');
document.querySelectorAll('[data-open-search]').forEach(button=>button.addEventListener('click',()=>openDialog(searchDialog)));
const search=document.querySelector('[data-search-input]');
search?.addEventListener('input',()=>{const query=search.value.trim().toLocaleLowerCase('ru');let count=0;document.querySelectorAll('[data-search-item]').forEach(item=>{item.hidden=!item.dataset.searchText.toLocaleLowerCase('ru').includes(query);if(!item.hidden)count++;});document.querySelector('[data-search-empty]').hidden=count>0;});
const cookieDialog=document.querySelector('[data-cookie-dialog]');
document.querySelectorAll('[data-open-cookies]').forEach(button=>button.addEventListener('click',()=>openDialog(cookieDialog)));
document.querySelectorAll('[data-cookie-choice]').forEach(button=>button.addEventListener('click',()=>{try{localStorage.setItem('aerzen-cookie-preferences',JSON.stringify({choice:button.dataset.cookieChoice,version:1,updatedAt:new Date().toISOString()}));}catch{}document.querySelector('[data-cookie-status]').textContent='Выбор сохранён. Дополнительные сервисы не подключены.';}));
document.querySelectorAll('[data-print]').forEach(button=>button.addEventListener('click',()=>window.print()));
document.querySelectorAll('[data-request-form]').forEach(form=>{
 form.addEventListener('submit',event=>{const email=form.querySelector('[name=email]');const phone=form.querySelector('[name=phone]');if(!email.value.trim()&&!phone.value.trim()){event.preventDefault();form.classList.add('form-invalid');phone.setCustomValidity('Укажите телефон или e-mail, чтобы мы могли ответить.');phone.reportValidity();return;}phone.setCustomValidity('');const button=form.querySelector('[type=submit]');if(button){button.disabled=true;button.setAttribute('aria-busy','true');form.querySelector('.form-feedback').textContent='Отправляем…';}});
 form.querySelectorAll('[name=phone],[name=email]').forEach(input=>input.addEventListener('input',()=>form.querySelector('[name=phone]').setCustomValidity('')));
});
const assembly=document.querySelector('[data-blower-section]');
if(assembly){
 const caption=document.querySelector('[data-scene-caption]');
 assembly.addEventListener('blower:progress',event=>{const {progress}=event.detail;caption.textContent=progress<.25?'Агрегат в сборе':progress<.56?'Разборка':progress<.70?'Корпус. Роторы. Привод.':progress<.92?'Сборка':'Единая система';});
 import('./blower-scene.js').then(({initBlowerScene})=>initBlowerScene({canvas:'[data-blower-canvas]',section:'[data-blower-section]',poster:'[data-blower-poster]'})).catch(()=>{assembly.dataset.motionState='static';});
}
window.addEventListener('pageshow',()=>document.querySelectorAll('[data-request-form] [aria-busy]').forEach(b=>{b.disabled=false;b.removeAttribute('aria-busy');}));
