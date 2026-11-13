const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
function runtime(language){
 const elements={};for(const id of ['companyContext','countBadge','pendingList'])elements[id]={innerHTML:'',textContent:'',appendChild(x){this.innerHTML+=x.innerHTML;},querySelectorAll(){return [];}};
 const listeners={};const c={URL,Date,console,localStorage:{getItem(){return null;},setItem(){}},location:{href:'https://example.invalid/?lang='+language},navigator:{onLine:true},document:{documentElement:{},addEventListener(k,v){listeners[k]=v;},getElementById(id){return elements[id];},createElement(){return {innerHTML:''};}},confirm:()=>true,setTimeout(){},sessionStorage:{getItem(){return null;}}};c.window=c;c.addEventListener=()=>{};vm.createContext(c);vm.runInContext(fs.readFileSync('locale.js','utf8'),c);vm.runInContext(fs.readFileSync('app.js','utf8').replace(/init\(\)\.catch[\s\S]*$/,''),c);return {c,elements};
}
test('offline rendering translates captions and preserves instrument data',async()=>{
 for(const language of ['en','es']){
  const {c,elements}=runtime(language);c.renderCompanyContext();assert.ok(!elements.companyContext.innerHTML.includes('Nenhuma empresa'));
  c.getAllPending=async()=>[{id:1,tag:'PT-001',name:'Pressão',sector:'Setor',location:'Localização',created_at:'2026-11-04T12:00:00Z',photo_blob:new Blob()}];
  await c.renderPending();assert.ok(elements.pendingList.innerHTML.includes('Pressão'));assert.ok(!elements.pendingList.innerHTML.includes('Salvo:'));assert.ok(!elements.countBadge.textContent.includes('pendente'));
  assert.equal(c.tcH('<option>Manutenção</option>').includes('value="Manutenção"'),true);
 }
});
test('offline shell loads language runtime first and retains canonical status values',()=>{
 const html=fs.readFileSync('index.html','utf8');assert.ok(html.indexOf('locale.js')<html.indexOf('app.js'));for(const status of ['Ativo','Sem serviço','Manutenção','Inativo'])assert.ok(html.includes('value="'+status+'"'));assert.ok(fs.readFileSync('sw.js','utf8').includes('./locale.js?v=20261113-sync'));
});

test('sync keeps the registration after a network failure and clears it after confirmation', async () => {
 const { c, elements } = runtime('pt-BR');
 Object.assign(c, { AbortController, FormData, clearTimeout() {} });
 elements.syncBtn = { disabled: false };
 elements.toast = { classList: { add() {}, remove() {} } };
 const company = { company_id: 5 };
 let pending = [{ id: 1, company_id: 5, tag: 'PT-001', photo_blob: new Blob(['photo']) }];
 let requests = 0;
 c.currentContext = () => company;
 c.currentToken = () => 'test-token';
 c.getAllPending = async () => pending;
 c.renderPending = async () => {};
 c.deletePending = async (id, context) => {
  assert.equal(context, company);
  pending = pending.filter(item => item.id !== id);
 };
 c.fetch = async (url, options) => {
  requests++;
  assert.match(url, /\/equipment$/);
  assert.equal(options.method, 'POST');
  assert.equal(options.body.get('tag'), 'PT-001');
  assert.equal(options.body.get('photo').size, 5);
  if (requests === 1) throw new TypeError('Failed to fetch');
  return { ok: true, json: async () => ({ id: 21, tag: 'PT-001' }) };
 };

 await c.syncPending(1);
 assert.equal(pending.length, 1);
 assert.match(elements.toast.textContent, /continua na fila/);
 assert.equal(elements.syncBtn.disabled, false);

 await c.syncPending(1);
 assert.equal(pending.length, 0);
 assert.match(elements.toast.textContent, /Cadastro enviado/);
 assert.equal(requests, 2);
});
