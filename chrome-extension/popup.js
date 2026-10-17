const CHECKOUT_URL = 'https://audidefuehrungen2.regiondo.de/checkout/cart';
const COOKIE_DOMAIN = 'audidefuehrungen2.regiondo.de';
const CAT_LABELS = ['Kat3-237', 'Kat1-136', 'Kat1-328'];

const $ = (id) => document.getElementById(id);

const DEFAULT_SERVER = 'http://51.20.185.59';
let authToken = null;

// Load saved settings
chrome.storage.local.get(['serverUrl', 'authToken'], (data) => {
  $('serverUrl').value = data.serverUrl || DEFAULT_SERVER;
  if (data.authToken) {
    authToken = data.authToken;
    showLoggedIn();
  }
});

$('serverUrl').addEventListener('change', () => {
  chrome.storage.local.set({ serverUrl: $('serverUrl').value });
});

function showLoggedIn() {
  $('loginSection').style.display = 'none';
  $('loggedInSection').style.display = 'block';
}

function showLoggedOut() {
  $('loginSection').style.display = 'block';
  $('loggedInSection').style.display = 'none';
  $('cartsSection').style.display = 'none';
}

// Login
$('loginBtn').addEventListener('click', async () => {
  const server = $('serverUrl').value.replace(/\/$/, '');
  const password = $('password').value;
  if (!server || !password) { showStatus('Server und Passwort eingeben', 'error'); return; }

  try {
    $('loginBtn').disabled = true;
    $('loginBtn').textContent = 'Login...';
    const resp = await fetch(`${server}/api/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ password })
    });
    const data = await resp.json();
    if (data.success && data.token) {
      authToken = data.token;
      chrome.storage.local.set({ serverUrl: server, authToken });
      $('password').value = '';
      showLoggedIn();
      showStatus('Eingeloggt!', 'success');
      $('fetchBtn').click();
    } else {
      showStatus(data.message || 'Login fehlgeschlagen', 'error');
    }
  } catch (e) {
    showStatus('Verbindungsfehler: ' + e.message, 'error');
  } finally {
    $('loginBtn').disabled = false;
    $('loginBtn').textContent = 'Login & Carts laden';
  }
});

// Logout
$('logoutBtn').addEventListener('click', () => {
  authToken = null;
  chrome.storage.local.remove('authToken');
  showLoggedOut();
  showStatus('Ausgeloggt', 'success');
});

// Enter key on password field
$('password').addEventListener('keydown', (e) => {
  if (e.key === 'Enter') $('loginBtn').click();
});

function showStatus(msg, type) {
  const el = $('status');
  el.textContent = msg;
  el.className = 'status ' + type;
}

function getTimeRemaining(expiresAt) {
  const diff = Math.max(0, new Date(expiresAt) - new Date());
  const min = Math.floor(diff / 60000);
  const sec = Math.floor((diff % 60000) / 1000);
  return `${min}:${sec.toString().padStart(2, '0')}`;
}

// Fetch carts from server
$('fetchBtn').addEventListener('click', async () => {
  const server = $('serverUrl').value.replace(/\/$/, '');

  if (!server || !authToken) {
    showStatus('Bitte erst einloggen', 'error');
    return;
  }

  try {
    $('fetchBtn').disabled = true;
    $('fetchBtn').textContent = 'Laden...';

    const resp = await fetch(`${server}/api/carts`, {
      headers: { 'X-Auth-Token': authToken }
    });

    if (resp.status === 401) {
      authToken = null;
      chrome.storage.local.remove('authToken');
      showLoggedOut();
      showStatus('Session abgelaufen, bitte neu einloggen', 'error');
      return;
    }
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const carts = await resp.json();

    // Filter active carts
    const now = new Date();
    const active = carts.filter(c => {
      const exp = new Date(c.expires_at.endsWith('Z') ? c.expires_at : c.expires_at + 'Z');
      return exp > now;
    });

    if (active.length === 0) {
      showStatus('Keine aktiven Carts', 'error');
      $('cartsSection').style.display = 'none';
      return;
    }

    // Render cart list
    const list = $('cartsList');
    list.innerHTML = '';
    $('cartsSection').style.display = 'block';

    for (const cart of active) {
      const expStr = cart.expires_at.endsWith('Z') ? cart.expires_at : cart.expires_at + 'Z';
      const remaining = getTimeRemaining(expStr);
      const catLabel = CAT_LABELS[cart.price_category] || `Cat ${cart.price_category}`;

      const div = document.createElement('div');
      div.className = 'cart-item';
      div.innerHTML = `
        <span class="timer">${remaining}</span>
        <div class="cat">${catLabel} — ${cart.quantity}x</div>
        <div class="meta">${cart.total_time ? cart.total_time.toFixed(2) + 's' : ''}</div>
      `;
      div.addEventListener('click', () => doCheckout(server, cart.token));
      list.appendChild(div);
    }

    showStatus(`${active.length} aktive Cart(s) gefunden`, 'success');
  } catch (e) {
    showStatus('Fehler: ' + e.message, 'error');
  } finally {
    $('fetchBtn').disabled = false;
    $('fetchBtn').textContent = 'Carts laden';
  }
});

// Manual token checkout
$('checkoutBtn').addEventListener('click', () => {
  const server = $('serverUrl').value.replace(/\/$/, '');
  const cartToken = $('tokenInput').value.trim();
  if (!server || !cartToken) {
    showStatus('Server URL und Cart Token eingeben', 'error');
    return;
  }
  doCheckout(server, cartToken);
});

async function doCheckout(server, cartToken) {
  try {
    showStatus('Cookie wird gesetzt...', 'success');

    // Fetch cookie data from API
    const resp = await fetch(`${server}/api/checkout/${cartToken}/cookie`);
    if (!resp.ok) {
      if (resp.status === 410) throw new Error('Cart abgelaufen');
      throw new Error(`HTTP ${resp.status}`);
    }
    const data = await resp.json();

    // Set cookie using chrome.cookies API (can override HttpOnly!)
    await chrome.cookies.set({
      url: `https://${COOKIE_DOMAIN}/`,
      name: data.name,
      value: data.value,
      domain: `.${COOKIE_DOMAIN}`,
      path: '/',
      secure: true,
      httpOnly: true,
      sameSite: 'lax'
    });

    showStatus('Cookie gesetzt! Weiterleitung...', 'success');

    // Open checkout in new tab
    chrome.tabs.create({ url: CHECKOUT_URL });

  } catch (e) {
    showStatus('Fehler: ' + e.message, 'error');
  }
}
