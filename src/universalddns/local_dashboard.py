"""Local-only, read-only dashboard resources; bearer tokens stay in page memory.

The browser calls existing scoped APIs. No new administrative authority exists.
"""
from ipaddress import ip_address

from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse, Response


def require_loopback(request: Request) -> None:
    """Never expose dashboard pages on a non-loopback transport."""
    host = request.client.host if request.client is not None else ""
    try:
        if not ip_address(host).is_loopback:
            raise HTTPException(403, "local dashboard only")
    except ValueError as exc:
        raise HTTPException(403, "local dashboard only") from exc


PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>UniversalDDNSServer · Local dashboard</title>
<style>
body{font-family:system-ui,sans-serif;max-width:64rem;margin:2rem auto;padding:0 1rem;
background:#f8fafc;color:#17212b}h1{font-size:1.7rem}input,button{font:inherit;padding:.5rem}
label{display:block;margin:.8rem 0}input{width:min(100%,36rem);box-sizing:border-box}
button{margin:.4rem .4rem .4rem 0;cursor:pointer}
table{border-collapse:collapse;width:100%;background:white}th,td{border:1px solid #bbc4cc;
padding:.55rem;text-align:left;overflow-wrap:anywhere}th{background:#e8edf2}
#message{min-height:2rem}small{display:block;margin:1rem 0}
</style></head><body>
<h1>UniversalDDNSServer</h1>
<p>Local read-only dashboard. Displays only records permitted by the supplied
token. Updates and administration are not available here.</p>
<label for="token">Scoped bearer token (kept in this page only)</label>
<input id="token" type="password" autocomplete="off" spellcheck="false">
<div><button id="load" type="button">Load permitted records</button>
<button id="clear" type="button">Clear token and results</button></div>
<p id="message" role="status" aria-live="polite"></p>
<table><caption>Records available to this credential</caption>
<thead><tr><th>ID</th><th>DNS name</th><th>Type</th><th>TTL (seconds)</th></tr></thead>
<tbody id="records"></tbody></table>
<h2>Record details and DNS observation</h2>
<label for="detail-id">Permitted record ID</label>
<input id="detail-id" type="text" autocomplete="off">
<button id="detail-load" type="button">Inspect record</button>
<p id="detail-status" role="status" aria-live="polite"></p>
<dl id="detail-results"></dl>
<p>DNS observation is unavailable unless a trusted read-only observer is configured.
A matching template is not proof that a particular update intent succeeded.</p>
<h2>Recent update intents</h2>
<p>Newest 20 updates owned by this credential for records it can currently access.</p>
<label for="history-record">Record ID (optional)</label>
<input id="history-record" type="text" autocomplete="off" placeholder="All permitted records">
<label for="history-state">Status</label>
<select id="history-state"><option value="">All statuses</option>
<option value="pending">Pending</option><option value="applying">Applying</option>
<option value="applied">Applied</option><option value="failed">Failed</option></select>
<button id="history-load" type="button">Load recent updates</button>
<p id="history-overview" role="status" aria-live="polite"></p>
<p id="history-message" role="status" aria-live="polite"></p>
<table><caption>Recent permitted updates</caption>
<thead><tr><th>Submitted (UTC)</th><th>Record ID</th><th>Status</th><th>Intent ID</th></tr></thead>
<tbody id="history"></tbody></table>
<h2>Check a known update intent</h2>
<p>You can enter an ID from recent history or another known intent ID.</p>
<label for="intent">Intent identifier</label>
<input id="intent" type="text" autocomplete="off">
<button id="lookup" type="button">Check intent</button>
<p id="intent-status" role="status" aria-live="polite"></p>
<small>Pending means queued, not published. This page does not display inactive
catalog records or independently establish server or DNS health.</small>
<script src="/dashboard/app.js" defer></script></body></html>"""

SCRIPT = """'use strict';
(() => {
  const byId = id => document.getElementById(id);
  const rows = byId('records');
  const history = byId('history');
  const message = byId('message');
  const intentStatus = byId('intent-status');
  function clearRows() { rows.replaceChildren(); }
  function clearHistory() { history.replaceChildren(); }
  function setMessage(target, value) { target.textContent = value; }
  async function query(path) {
    const token = byId('token').value;
    if (!token) throw new Error('Enter a scoped bearer token.');
    const response = await fetch(path, {
      headers: {'Authorization': 'Bearer ' + token},
      cache: 'no-store',
      credentials: 'omit'
    });
    if (!response.ok) throw new Error('Request denied or unavailable (HTTP ' + response.status + ').');
    return response.json();
  }
  byId('load').addEventListener('click', async () => {
    clearRows();
    setMessage(message, 'Loading…');
    try {
      const data = await query('/api/v1/records');
      if (!Array.isArray(data.records)) throw new Error('Invalid API response.');
      for (const record of data.records) {
        const tr = document.createElement('tr');
        for (const key of ['id', 'name', 'type', 'ttl']) {
          const td = document.createElement('td');
          td.textContent = String(record[key] ?? '');
          tr.appendChild(td);
        }
        rows.appendChild(tr);
      }
      setMessage(message, data.records.length + ' permitted record(s).');
    } catch (error) { setMessage(message, error.message); }
  });
  byId('detail-load').addEventListener('click', async () => {
    const details = byId('detail-results');
    details.replaceChildren();
    setMessage(byId('detail-status'), 'Loading…');
    const id = byId('detail-id').value.trim();
    if (!id) {
      setMessage(byId('detail-status'), 'Enter a permitted record ID.');
      return;
    }
    try {
      const data = await query('/api/v1/records/' + encodeURIComponent(id));
      const record = data.record || {};
      const fields = [
        ['Record ID', record.id], ['Zone', record.zone],
        ['Name', record.name], ['Type', record.type],
        ['TTL (seconds)', record.ttl],
        ['Authoritative DNS observation', (data.authoritative || {}).status || 'unavailable']
      ];
      for (const [name, value] of fields) {
        const dt = document.createElement('dt');
        const dd = document.createElement('dd');
        dt.textContent = name;
        dd.textContent = String(value ?? '');
        details.append(dt, dd);
      }
      setMessage(byId('detail-status'), 'Record details retrieved.');
    } catch (error) {
      setMessage(byId('detail-status'), error.message);
    }
  });
  byId('history-load').addEventListener('click', async () => {
    clearHistory();
    setMessage(byId('history-overview'), '');
    setMessage(byId('history-message'), 'Loading…');
    try {
      const params = new URLSearchParams({limit: '20'});
      const record = byId('history-record').value.trim();
      if (record) params.set('record_id', record);
      const state = byId('history-state').value;
      if (state) params.set('state', state);
      const data = await query('/api/v1/intents?' + params.toString());
      if (!Array.isArray(data.intents)) throw new Error('Invalid API response.');
      for (const item of data.intents) {
        const tr = document.createElement('tr');
        for (const key of ['created_at', 'record_id', 'status', 'intent_id']) {
          const td = document.createElement('td');
          td.textContent = String(item[key] ?? '');
          tr.appendChild(td);
        }
        history.appendChild(tr);
      }
      const counts = {pending: 0, applying: 0, applied: 0, failed: 0};
      for (const item of data.intents) {
        if (Object.prototype.hasOwnProperty.call(counts, item.status)) counts[item.status]++;
      }
      setMessage(byId('history-overview'), 'In displayed page: ' +
        Object.entries(counts).map(([key, value]) => key + ' ' + value).join(' · '));
      setMessage(byId('history-message'), data.intents.length +
        ' recent update(s) matching filters (maximum 20 shown).');
    } catch (error) { setMessage(byId('history-message'), error.message); }
  });
  byId('lookup').addEventListener('click', async () => {
    setMessage(intentStatus, 'Checking…');
    const identifier = byId('intent').value.trim();
    if (!/^[0-9a-fA-F-]{36}$/.test(identifier)) {
      setMessage(intentStatus, 'Enter a valid intent UUID.');
      return;
    }
    try {
      const data = await query('/api/v1/intents/' + encodeURIComponent(identifier));
      setMessage(intentStatus, 'Intent status: ' + String(data.status ?? 'unknown'));
    } catch (error) { setMessage(intentStatus, error.message); }
  });
  byId('clear').addEventListener('click', () => {
    byId('token').value = '';
    byId('intent').value = '';
    byId('detail-id').value = '';
    byId('detail-results').replaceChildren();
    setMessage(byId('detail-status'), '');
    clearRows();
    clearHistory();
    byId('history-record').value = '';
    byId('history-state').value = '';
    setMessage(byId('history-overview'), '');
    setMessage(byId('history-message'), '');
    setMessage(message, 'Token and displayed results cleared.');
    setMessage(intentStatus, '');
  });
})();
"""


def dashboard(request: Request) -> HTMLResponse:
    require_loopback(request)
    return HTMLResponse(PAGE, headers={
        "Cache-Control": "no-store",
        "X-Content-Type-Options": "nosniff",
        "Referrer-Policy": "no-referrer",
        "Content-Security-Policy": "default-src 'none'; script-src 'self'; "
        "style-src 'unsafe-inline'; connect-src 'self'; base-uri 'none'; "
        "form-action 'none'; frame-ancestors 'none'",
    })


def dashboard_script(request: Request) -> Response:
    require_loopback(request)
    return Response(SCRIPT, media_type="application/javascript", headers={
        "Cache-Control": "no-store",
        "X-Content-Type-Options": "nosniff",
    })
