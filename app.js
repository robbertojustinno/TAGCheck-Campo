const DB_PREFIX = 'tagcheck_campo_offline_v2_company_';
const STORE = 'pending_equipment';
const CONTEXT_KEY = 'tagcheck_campo_active_context_v2';
const TOKEN_KEY = 'tagcheck_campo_session_token_v2';
const DEFAULT_API = 'https://tagcheck-fase2-hml-api.onrender.com';
const ALLOWED_ADMIN_ORIGINS = new Set([
  'https://tagcheck-fase2-hml-admin.onrender.com',
  'http://localhost',
  'http://127.0.0.1'
]);

let db = null;
let dbCompanyId = null;
let deferredPrompt;

const $ = id => document.getElementById(id);

function toast(msg, type='') {
  const el = $('toast');
  el.textContent = msg;
  el.className = `toast ${type}`;
  el.classList.remove('hidden');
  setTimeout(() => el.classList.add('hidden'), 3500);
}

function escapeHtml(v) {
  return String(v ?? '').replace(/[&<>"']/g, m => ({
    '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'
  }[m]));
}

function parseJwt(token) {
  try {
    const part = String(token || '').split('.')[1];
    if (!part) return null;
    const normalized = part.replace(/-/g, '+').replace(/_/g, '/');
    return JSON.parse(atob(normalized.padEnd(Math.ceil(normalized.length / 4) * 4, '=')));
  } catch {
    return null;
  }
}

function tokenExpiryMs(token) {
  const payload = parseJwt(token);
  return Number(payload?.exp || 0) * 1000;
}

function normalizeContext(raw) {
  const companyId = Number(raw?.company_id);
  if (!Number.isInteger(companyId) || companyId <= 0) return null;
  return {
    company_id: companyId,
    company_name: String(raw?.company_name || ''),
    user_id: raw?.user_id == null ? null : Number(raw.user_id),
    email: String(raw?.email || ''),
    role: String(raw?.role || ''),
    expires_at: Number(raw?.expires_at || 0)
  };
}

function saveContext(raw) {
  const context = normalizeContext(raw);
  if (!context) throw new Error('Contexto da empresa inválido.');
  localStorage.setItem(CONTEXT_KEY, JSON.stringify(context));
  renderCompanyContext();
  return context;
}

function currentContext({ allowExpired=false } = {}) {
  try {
    const context = normalizeContext(JSON.parse(localStorage.getItem(CONTEXT_KEY) || 'null'));
    if (!context) return null;
    if (!allowExpired && context.expires_at && Date.now() >= context.expires_at) return null;
    return context;
  } catch {
    return null;
  }
}

function currentToken() {
  return sessionStorage.getItem(TOKEN_KEY) || '';
}

function setSession(token, context) {
  if (!token) throw new Error('Sessão inválida.');
  const claims = parseJwt(token);
  const tokenCompany = claims?.company_id == null ? null : Number(claims.company_id);
  const normalized = normalizeContext(context);
  if (!normalized) throw new Error('Empresa da sessão inválida.');
  if (tokenCompany != null && tokenCompany !== normalized.company_id) {
    throw new Error('Empresa do token não corresponde à empresa selecionada.');
  }
  sessionStorage.setItem(TOKEN_KEY, token);
  normalized.expires_at = normalized.expires_at || tokenExpiryMs(token);
  saveContext(normalized);
  return normalized;
}

function clearSession() {
  sessionStorage.removeItem(TOKEN_KEY);
}

function dbName(companyId) {
  const id = Number(companyId);
  if (!Number.isInteger(id) || id <= 0) throw new Error('Empresa offline inválida.');
  return `${DB_PREFIX}${id}`;
}

async function openDb(companyId) {
  const id = Number(companyId);
  if (db && dbCompanyId === id) return db;
  if (db) db.close();

  db = await new Promise((resolve, reject) => {
    const req = indexedDB.open(dbName(id), 1);
    req.onupgradeneeded = () => {
      const database = req.result;
      if (!database.objectStoreNames.contains(STORE)) {
        const store = database.createObjectStore(STORE, { keyPath: 'id', autoIncrement: true });
        store.createIndex('tag', 'tag', { unique: false });
        store.createIndex('created_at', 'created_at', { unique: false });
        store.createIndex('company_id', 'company_id', { unique: false });
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(new Error(`Falha no armazenamento offline local (${req.error?.name || 'erro desconhecido'}).`));
  });
  dbCompanyId = id;
  return db;
}

async function storeRequest(mode, fn) {
  const context = currentContext();
  if (!context) throw new Error('Empresa offline não validada ou sessão expirada.');
  const database = await openDb(context.company_id);
  return new Promise((resolve, reject) => {
    const tx = database.transaction(STORE, mode);
    const store = tx.objectStore(STORE);
    let result;
    try { result = fn(store); }
    catch (error) { reject(error); return; }
    tx.oncomplete = () => resolve(result);
    tx.onerror = () => reject(tx.error || new Error('Falha no armazenamento offline.'));
    tx.onabort = () => reject(tx.error || new Error('Transação offline cancelada.'));
  });
}

async function getAllPending() {
  const context = currentContext();
  if (!context) return [];
  const database = await openDb(context.company_id);
  const rows = await new Promise((resolve, reject) => {
    const req = database.transaction(STORE, 'readonly').objectStore(STORE).getAll();
    req.onsuccess = () => resolve(req.result || []);
    req.onerror = () => reject(req.error);
  });
  return rows.filter(item => Number(item.company_id) === context.company_id);
}

async function addPending(item) {
  const context = currentContext();
  if (!context) throw new Error('Entre online no Admin e selecione a empresa antes de cadastrar offline.');
  item.company_id = context.company_id;
  item.user_id = context.user_id;
  const database = await openDb(context.company_id);
  return new Promise((resolve, reject) => {
    const req = database.transaction(STORE, 'readwrite').objectStore(STORE).add(item);
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

async function deletePending(id) {
  const context = currentContext();
  if (!context) throw new Error('Empresa offline inválida.');
  const database = await openDb(context.company_id);
  const item = await new Promise((resolve, reject) => {
    const req = database.transaction(STORE, 'readonly').objectStore(STORE).get(Number(id));
    req.onsuccess = () => resolve(req.result || null);
    req.onerror = () => reject(req.error);
  });
  if (!item || Number(item.company_id) !== context.company_id) throw new Error('Cadastro não pertence à empresa ativa.');
  return new Promise((resolve, reject) => {
    const req = database.transaction(STORE, 'readwrite').objectStore(STORE).delete(Number(id));
    req.onsuccess = () => resolve();
    req.onerror = () => reject(req.error);
  });
}

function loadConfig() {
  $('apiBase').value = DEFAULT_API;
  $('apiBase').readOnly = true;
  const context = currentContext({allowExpired:true});
  $('loginUser').value = context?.email || '';
  renderCompanyContext();
}

function renderCompanyContext() {
  const box = $('companyContext');
  if (!box) return;
  const context = currentContext({allowExpired:true});
  if (!context) {
    box.innerHTML = '<strong>Nenhuma empresa validada.</strong><br><span class="small">Abra este cadastro pelo Admin V2 para vincular a empresa.</span>';
    return;
  }
  const expired = context.expires_at && Date.now() >= context.expires_at;
  box.innerHTML = `<strong>Empresa ativa:</strong> ${escapeHtml(context.company_name || ('ID ' + context.company_id))}
    <br><span class="small">ID interno: ${context.company_id}${expired ? ' • sessão expirada: conecte e reabra pelo Admin' : ''}</span>`;
}

function updateNetworkStatus() {
  const el = $('netStatus');
  if (navigator.onLine) {
    el.textContent = 'Online';
    el.className = 'status-pill ok';
  } else {
    el.textContent = 'Offline';
    el.className = 'status-pill off';
  }
}

async function renderPending() {
  const list = await getAllPending();
  $('countBadge').textContent = `${list.length} pendente${list.length === 1 ? '' : 's'}`;
  const box = $('pendingList');
  if (!list.length) {
    box.innerHTML = '<p class="small">Nenhum cadastro pendente nesta empresa.</p>';
    return;
  }
  box.innerHTML = '';
  for (const item of list.sort((a,b)=>(b.created_at||'').localeCompare(a.created_at||''))) {
    const url = URL.createObjectURL(item.photo_blob);
    const div = document.createElement('div');
    div.className = 'pending-item';
    div.innerHTML = `
      <img src="${url}" alt="Foto">
      <div>
        <h4>${escapeHtml(item.tag)} — ${escapeHtml(item.name)}</h4>
        <p>${escapeHtml(item.sector || '-')} • ${escapeHtml(item.location || '-')}</p>
        <p>Salvo: ${new Date(item.created_at).toLocaleString('pt-BR')}</p>
      </div>
      <div class="mini-actions">
        <button class="secondary" data-sync="${item.id}">Enviar</button>
        <button class="outline" data-del="${item.id}">Excluir</button>
      </div>`;
    box.appendChild(div);
  }
  box.querySelectorAll('[data-del]').forEach(btn => btn.onclick = async () => {
    if (confirm('Excluir este cadastro pendente desta empresa?')) {
      await deletePending(btn.dataset.del);
      await renderPending();
      toast('Cadastro pendente excluído.');
    }
  });
  box.querySelectorAll('[data-sync]').forEach(btn => btn.onclick = async () => syncOne(Number(btn.dataset.sync)));
}

function clearForm() {
  $('equipmentForm').reset();
  $('preview').src = '';
  $('preview').classList.add('hidden');
}

async function fileToBlob(file) {
  return new Blob([await file.arrayBuffer()], { type: file.type || 'image/jpeg' });
}

async function saveOffline(event) {
  event.preventDefault();
  const context = currentContext();
  if (!context) {
    toast('Empresa não validada. Abra o Cadastro Offline pelo Admin V2 com internet pelo menos uma vez.', 'error');
    return;
  }

  const photo = $('photo').files[0];
  if (!photo) { toast('Selecione ou tire uma foto.', 'error'); return; }
  const tag = $('tag').value.trim().toUpperCase();
  const name = $('name').value.trim();
  if (!tag || !name) { toast('TAG e Nome são obrigatórios.', 'error'); return; }

  const item = {
    company_id: context.company_id,
    user_id: context.user_id,
    tag,
    name,
    equipment_type: $('equipment_type').value.trim(),
    sector: $('sector').value.trim(),
    location: $('location').value.trim(),
    manufacturer: $('manufacturer').value.trim(),
    model: $('model').value.trim(),
    serial_number: $('serial_number').value.trim(),
    calibration_date: $('calibration_date').value || '',
    next_calibration_date: $('next_calibration_date').value || '',
    status: $('status').value.trim() || 'Ativo',
    notes: $('notes').value.trim(),
    photo_name: `${tag}.jpg`,
    photo_type: photo.type || 'image/jpeg',
    photo_blob: await fileToBlob(photo),
    created_at: new Date().toISOString(),
    synced_at: ''
  };
  await addPending(item);
  clearForm();
  await renderPending();
  toast(`Salvo offline em ${context.company_name || 'empresa atual'}.`, 'ok');
}

function buildFormData(item) {
  const fd = new FormData();
  ['tag','name','equipment_type','sector','location','manufacturer','model','serial_number','calibration_date','next_calibration_date','status','notes']
    .forEach(k => fd.append(k, item[k] || ''));
  fd.append('photo', item.photo_blob, item.photo_name || `${item.tag}.jpg`);
  return fd;
}

async function apiFetch(path, options={}) {
  const token = currentToken();
  if (!token) throw new Error('Sessão online ausente. Reabra pelo Admin V2 antes de sincronizar.');
  const context = currentContext();
  if (!context) throw new Error('Empresa ativa inválida ou expirada.');

  const claims = parseJwt(token);
  if (claims?.company_id != null && Number(claims.company_id) !== context.company_id) {
    clearSession();
    throw new Error('Empresa do token não corresponde à empresa ativa.');
  }

  const headers = { ...(options.headers || {}), Authorization: `Bearer ${token}` };
  const res = await fetch(`${DEFAULT_API}${path}`, { ...options, headers, cache:'no-store' });
  let data = null;
  try { data = await res.json(); } catch (_) {}
  if (!res.ok) {
    const msg = data?.detail || `Erro HTTP ${res.status}`;
    const err = new Error(typeof msg === 'string' ? msg : JSON.stringify(msg));
    err.status = res.status;
    throw err;
  }
  return data;
}

async function syncItem(item) {
  const context = currentContext();
  if (!context || Number(item.company_id) !== context.company_id) {
    throw new Error('Bloqueado: cadastro pertence a outra empresa.');
  }
  try {
    await apiFetch('/equipment', { method: 'POST', body: buildFormData(item) });
    return 'created';
  } catch (err) {
    const msg = String(err.message || '').toLowerCase();
    if (err.status === 400 && msg.includes('tag')) {
      const existing = await apiFetch(`/equipment/tag/${encodeURIComponent(item.tag)}`);
      await apiFetch(`/equipment/${existing.id}`, { method: 'PUT', body: buildFormData(item) });
      return 'updated';
    }
    throw err;
  }
}

async function syncOne(id) {
  if (!navigator.onLine) { toast('Sem internet para sincronizar.', 'error'); return; }
  const all = await getAllPending();
  const item = all.find(x => x.id === Number(id));
  if (!item) return;
  try {
    const action = await syncItem(item);
    await deletePending(id);
    await renderPending();
    toast(action === 'created' ? 'Cadastro enviado para a empresa ativa.' : 'TAG atualizada na empresa ativa.', 'ok');
  } catch (err) {
    toast(`Falha ao enviar ${item.tag}: ${err.message}`, 'error');
  }
}

async function syncAll() {
  if (!navigator.onLine) { toast('Sem internet para sincronizar.', 'error'); return; }
  const context = currentContext();
  if (!context) { toast('Empresa ativa inválida ou expirada.', 'error'); return; }
  const token = currentToken();
  if (!token) { toast('Reabra o Cadastro Offline pelo Admin V2 para renovar a sessão.', 'error'); return; }

  const all = await getAllPending();
  if (!all.length) { toast('Não há pendentes nesta empresa.', 'ok'); return; }
  let ok = 0, fail = 0;
  for (const item of all) {
    if (Number(item.company_id) !== context.company_id) { fail++; continue; }
    try {
      await syncItem(item);
      await deletePending(item.id);
      ok++;
    } catch (err) {
      console.error(item.tag, err);
      fail++;
      if (err.status === 401 || err.status === 403) break;
    }
  }
  await renderPending();
  toast(`Sincronização da empresa concluída. Enviados: ${ok}. Falhas: ${fail}.`, fail ? 'error' : 'ok');
}

async function validateTokenAndLoadIdentity(token) {
  const res = await fetch(`${DEFAULT_API}/auth/me`, {
    headers: { Authorization: `Bearer ${token}`, Accept:'application/json' },
    cache:'no-store'
  });
  if (!res.ok) throw new Error('Não foi possível validar a sessão da empresa.');
  return res.json();
}

async function login() {
  if (!navigator.onLine) { toast('O login inicial precisa de internet.', 'error'); return; }
  const username = $('loginUser').value.trim();
  const password = $('loginPass').value;
  if (!username || !password) { toast('Informe e-mail/usuário e senha.', 'error'); return; }
  try {
    const body = username.includes('@') ? { email: username, password } : { username, password };
    const res = await fetch(`${DEFAULT_API}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      cache:'no-store'
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Falha no login');
    if (data.requires_company_selection) {
      throw new Error('Este usuário possui mais de uma empresa. Entre pelo Admin V2, selecione a empresa e abra Cadastro Offline.');
    }
    const identity = await validateTokenAndLoadIdentity(data.token);
    setSession(data.token, {
      company_id: identity.company_id,
      company_name: identity.company_name,
      user_id: identity.user_id,
      email: identity.email || username,
      role: identity.role,
      expires_at: tokenExpiryMs(data.token)
    });
    await openDb(identity.company_id);
    await renderPending();
    toast(`Empresa ${identity.company_name} validada.`, 'ok');
  } catch (err) {
    toast(err.message, 'error');
  }
}

function isAllowedAdminOrigin(origin) {
  if (ALLOWED_ADMIN_ORIGINS.has(origin)) return true;
  try {
    const url = new URL(origin);
    return url.hostname === 'tagcheck-fase2-hml-admin.onrender.com';
  } catch {
    return false;
  }
}

window.addEventListener('message', async event => {
  if (!isAllowedAdminOrigin(event.origin)) return;
  const data = event.data;
  if (!data || data.type !== 'TAGCHECK_CAMPO_SESSION') return;
  try {
    const context = setSession(data.token, {
      company_id: data.company_id,
      company_name: data.company_name,
      user_id: data.user_id,
      email: data.email,
      role: data.role,
      expires_at: data.expires_at || tokenExpiryMs(data.token)
    });
    await openDb(context.company_id);
    await renderPending();
    toast(`Cadastro Offline vinculado a ${context.company_name || 'empresa atual'}.`, 'ok');
    if (event.source && typeof event.source.postMessage === 'function') {
      event.source.postMessage({ type:'TAGCHECK_CAMPO_SESSION_ACK', company_id:context.company_id }, event.origin);
    }
  } catch (error) {
    toast(error.message, 'error');
  }
});

async function exportJson() {
  const context = currentContext();
  if (!context) { toast('Empresa não validada.', 'error'); return; }
  const all = await getAllPending();
  const serializable = [];
  for (const item of all) {
    const base64 = await blobToBase64(item.photo_blob);
    serializable.push({ ...item, photo_blob: base64 });
  }
  const blob = new Blob([JSON.stringify({
    tagcheck_export_version: 2,
    company_id: context.company_id,
    company_name: context.company_name,
    items: serializable
  }, null, 2)], { type:'application/json' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = `tagcheck_${context.company_id}_pendentes_${new Date().toISOString().slice(0,10)}.json`;
  a.click();
}

function blobToBase64(blob) {
  return new Promise(resolve => {
    const r = new FileReader();
    r.onload = () => resolve(r.result);
    r.readAsDataURL(blob);
  });
}

function base64ToBlob(dataUrl) {
  const [head,b64] = dataUrl.split(',');
  const mime = (head.match(/data:(.*);base64/)||[])[1] || 'image/jpeg';
  const bin = atob(b64);
  const arr = new Uint8Array(bin.length);
  for(let i=0;i<bin.length;i++) arr[i]=bin.charCodeAt(i);
  return new Blob([arr], {type:mime});
}

async function importJson(file) {
  const context = currentContext();
  if (!context) throw new Error('Empresa não validada.');
  const parsed = JSON.parse(await file.text());
  if (!parsed || Number(parsed.company_id) !== context.company_id || !Array.isArray(parsed.items)) {
    throw new Error('Backup pertence a outra empresa ou está em formato antigo. Importação bloqueada.');
  }
  for (const raw of parsed.items) {
    const item = { ...raw };
    if (Number(item.company_id) !== context.company_id) throw new Error('Backup contém dados de outra empresa.');
    item.photo_blob = typeof item.photo_blob === 'string' ? base64ToBlob(item.photo_blob) : item.photo_blob;
    delete item.id;
    await addPending(item);
  }
  await renderPending();
  toast('Backup desta empresa importado.', 'ok');
}

async function init() {
  loadConfig();
  updateNetworkStatus();

  const context = currentContext();
  if (context) {
    await openDb(context.company_id);
    await renderPending();
  } else {
    $('pendingList').innerHTML = '<p class="small">Abra pelo Admin V2 para ativar uma empresa neste dispositivo.</p>';
  }

  $('equipmentForm').addEventListener('submit', saveOffline);
  $('clearBtn').onclick = clearForm;
  $('syncBtn').onclick = syncAll;
  $('loginBtn').onclick = login;
  $('exportBtn').onclick = exportJson;
  $('importFile').onchange = e => e.target.files[0] && importJson(e.target.files[0]).catch(err => toast(err.message, 'error'));
  $('photo').onchange = () => {
    const file = $('photo').files[0];
    if (!file) return;
    $('preview').src = URL.createObjectURL(file);
    $('preview').classList.remove('hidden');
  };

  window.addEventListener('online', () => {
    updateNetworkStatus();
    renderCompanyContext();
  });
  window.addEventListener('offline', updateNetworkStatus);
  window.addEventListener('beforeinstallprompt', e => {
    e.preventDefault();
    deferredPrompt = e;
    $('installBtn').classList.remove('hidden');
  });
  $('installBtn').onclick = async () => {
    if (!deferredPrompt) return;
    deferredPrompt.prompt();
    await deferredPrompt.userChoice;
    deferredPrompt = null;
    $('installBtn').classList.add('hidden');
  };
  if ('serviceWorker' in navigator) navigator.serviceWorker.register('./sw.js', {updateViaCache:'none'}).catch(console.warn);
}

init().catch(err => toast(`Erro inicial: ${err.message}`, 'error'));
