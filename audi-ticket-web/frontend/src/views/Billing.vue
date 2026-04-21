<template>
  <div>
    <div class="view-head">
      <div>
        <div class="eyebrow">CHECKOUT IDENTITIES</div>
        <h1 class="view-title">Billing</h1>
      </div>
      <button @click="showModal = true" class="btn btn-primary">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
        <span>New profile</span>
      </button>
    </div>

    <div v-if="profiles.length === 0" class="empty">
      <div class="empty-mark">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><rect x="2.5" y="5.5" width="19" height="13" rx="2"/><path d="M2.5 10h19"/></svg>
      </div>
      <h3>No billing profiles</h3>
      <p>Create a profile to enable Auto Checkout.</p>
    </div>

    <div v-else class="profiles-grid">
      <article v-for="p in profiles" :key="p.id" class="profile-card">
        <div class="profile-top">
          <div class="profile-avatar mono">{{ initials(p.firstname, p.lastname) }}</div>
          <div class="profile-identity">
            <h3 class="profile-name">{{ p.name }}</h3>
            <p class="profile-legal mono">{{ p.firstname }} {{ p.lastname }}</p>
          </div>
          <div class="profile-actions">
            <button @click="editProfile(p)" class="icon-btn" aria-label="Edit">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
            </button>
            <button @click="deleteProfile(p.id)" class="icon-btn is-danger" aria-label="Delete">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-2 14a2 2 0 0 1-2 2H9a2 2 0 0 1-2-2L5 6"/></svg>
            </button>
          </div>
        </div>

        <dl class="profile-rows">
          <div><dt>Email</dt><dd class="mono">{{ p.email }}</dd></div>
          <div><dt>Phone</dt><dd class="mono">{{ p.telephone || '—' }}</dd></div>
          <div><dt>Stammnr.</dt><dd class="mono">{{ p.stammnummer || '—' }}</dd></div>
          <div>
            <dt>Card</dt>
            <dd class="mono" :class="{ 'is-empty': !p.has_card }">
              {{ p.has_card ? '•••• ' + p.card_last4 : 'not set' }}
            </dd>
          </div>
          <div>
            <dt>Invoice</dt>
            <dd :class="{ 'is-empty mono': !p.invoice_street }">
              {{ p.invoice_street ? p.invoice_street + ', ' + p.invoice_city : 'not set' }}
            </dd>
          </div>
        </dl>
      </article>
    </div>

    <!-- Modal -->
    <transition name="fade">
    <div v-if="showModal" class="modal-overlay" @click.self="closeModal">
      <div class="modal">
        <header class="modal-header">
          <div>
            <div class="modal-title">{{ editingId ? 'Edit profile' : 'New profile' }}</div>
            <div class="modal-sub">Used for Audi checkout + Stripe card tokenisation.</div>
          </div>
          <button @click="closeModal" class="icon-btn" aria-label="Close">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
          </button>
        </header>

        <div class="modal-body">
          <div class="form-section">
            <div class="form-section-title">Profile</div>
            <div class="field">
              <label class="field-label">Name <span class="req">*</span></label>
              <input v-model="form.name" placeholder="e.g. Leon, Mate">
            </div>
          </div>

          <div class="form-section">
            <div class="form-section-title">Personal</div>
            <div class="field-row">
              <div class="field"><label class="field-label">First <span class="req">*</span></label><input v-model="form.firstname"></div>
              <div class="field"><label class="field-label">Last <span class="req">*</span></label><input v-model="form.lastname"></div>
            </div>
            <div class="field"><label class="field-label">Email <span class="req">*</span></label><input v-model="form.email" type="email" inputmode="email"></div>
            <div class="field"><label class="field-label">Phone (incl. +49)</label><input v-model="form.telephone" type="tel" inputmode="tel" placeholder="+491721234567"></div>
            <div class="field-row">
              <div class="field"><label class="field-label">Stammnr. <span class="req">*</span></label><input v-model="form.stammnummer" inputmode="numeric"></div>
              <div class="field"><label class="field-label">Dept.</label><input v-model="form.department" placeholder="Optional"></div>
            </div>
          </div>

          <div class="form-section">
            <div class="form-section-title">Invoice address</div>
            <div class="field"><label class="field-label">Recipient</label><input v-model="form.invoice_recipient" placeholder="Default: first + last"></div>
            <div class="field-row">
              <div class="field"><label class="field-label">Company</label><input v-model="form.invoice_company" placeholder="Optional"></div>
              <div class="field"><label class="field-label">Tax ID</label><input v-model="form.invoice_tax_id" placeholder="Optional"></div>
            </div>
            <div class="field"><label class="field-label">Street</label><input v-model="form.invoice_street"></div>
            <div class="field-row">
              <div class="field"><label class="field-label">Postcode</label><input v-model="form.invoice_postcode" inputmode="numeric"></div>
              <div class="field"><label class="field-label">City</label><input v-model="form.invoice_city"></div>
            </div>
          </div>

          <div class="form-section">
            <div class="form-section-title">Card</div>
            <div class="field">
              <label class="field-label">Card number</label>
              <input v-model="form.card_number" class="mono" placeholder="4165 9834 2083 0861" maxlength="19" inputmode="numeric" autocomplete="off">
            </div>
            <div class="field-row-3">
              <div class="field"><label class="field-label">Month</label><input v-model="form.card_exp_month" class="mono" placeholder="MM" maxlength="2" inputmode="numeric"></div>
              <div class="field"><label class="field-label">Year</label><input v-model="form.card_exp_year" class="mono" placeholder="YY" maxlength="2" inputmode="numeric"></div>
              <div class="field"><label class="field-label">CVC</label><input v-model="form.card_cvc" class="mono" placeholder="•••" maxlength="4" type="password" inputmode="numeric"></div>
            </div>
          </div>
        </div>

        <footer class="modal-footer">
          <button @click="closeModal" class="btn btn-ghost">Cancel</button>
          <button @click="saveProfile" class="btn btn-primary" :disabled="saving">
            {{ saving ? 'Saving…' : 'Save profile' }}
          </button>
        </footer>
      </div>
    </div>
    </transition>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import { api } from '../stores/api';

const profiles = ref([]);
const showModal = ref(false);
const saving = ref(false);
const editingId = ref(null);
const emptyForm = {
  name: '', firstname: '', lastname: '', email: '', telephone: '',
  stammnummer: '', department: '',
  invoice_recipient: '', invoice_company: '', invoice_tax_id: '',
  invoice_street: '', invoice_postcode: '', invoice_city: '', invoice_country: 'DE',
  card_number: '', card_exp_month: '', card_exp_year: '', card_cvc: ''
};
const form = ref({ ...emptyForm });

const initials = (first = '', last = '') => ((first[0] || '') + (last[0] || '')).toUpperCase() || '—';

const fetchProfiles = async () => {
  try { profiles.value = await api.get('/api/billing/profiles'); } catch { /* ignore */ }
};

const editProfile = (p) => {
  editingId.value = p.id;
  form.value = {
    name: p.name, firstname: p.firstname, lastname: p.lastname,
    email: p.email, telephone: p.telephone,
    stammnummer: p.stammnummer, department: p.department || '',
    invoice_recipient: p.invoice_recipient || '', invoice_company: p.invoice_company || '',
    invoice_tax_id: p.invoice_tax_id || '', invoice_street: p.invoice_street || '',
    invoice_postcode: p.invoice_postcode || '', invoice_city: p.invoice_city || '',
    invoice_country: p.invoice_country || 'DE',
    card_number: '', card_exp_month: '', card_exp_year: '', card_cvc: ''
  };
  showModal.value = true;
};

const closeModal = () => {
  showModal.value = false;
  editingId.value = null;
  form.value = { ...emptyForm };
};

const saveProfile = async () => {
  if (!form.value.name || !form.value.firstname || !form.value.lastname || !form.value.email || !form.value.stammnummer) {
    alert('Please fill all required fields (Name, First, Last, Email, Stammnr.)');
    return;
  }
  saving.value = true;
  try {
    if (editingId.value) await api.request('PUT', `/api/billing/profiles/${editingId.value}`, form.value);
    else await api.post('/api/billing/profiles', form.value);
    await fetchProfiles();
    closeModal();
  } catch (e) {
    alert('Error: ' + (e.message || 'Unknown'));
  } finally {
    saving.value = false;
  }
};

const deleteProfile = async (id) => {
  if (!confirm('Delete profile?')) return;
  try {
    await api.delete(`/api/billing/profiles/${id}`);
    profiles.value = profiles.value.filter(p => p.id !== id);
  } catch (e) {
    alert('Error: ' + (e.message || 'Unknown'));
  }
};

onMounted(fetchProfiles);
</script>

<style scoped>
.view-head {
  display: flex; align-items: flex-end; justify-content: space-between;
  gap: 1rem;
  margin-bottom: 1.5rem;
}
.view-title {
  font-size: clamp(1.5rem, 4vw, 2rem);
  font-weight: 700;
  letter-spacing: -0.02em;
  line-height: 1.1;
  margin-top: 4px;
}

.profiles-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 12px;
}
@media (min-width: 640px) { .profiles-grid { grid-template-columns: repeat(2, 1fr); } }
@media (min-width: 1100px) { .profiles-grid { grid-template-columns: repeat(3, 1fr); } }

.profile-card {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  padding: 16px;
  transition: border-color 0.15s;
}
.profile-card:hover { border-color: color-mix(in oklab, var(--ink) 30%, var(--line)); }

.profile-top {
  display: flex; align-items: center; gap: 12px;
  margin-bottom: 14px;
}
.profile-avatar {
  width: 44px; height: 44px;
  border-radius: 10px;
  background: var(--signal);
  color: var(--signal-ink);
  display: flex; align-items: center; justify-content: center;
  font-size: 0.875rem; font-weight: 700;
  flex-shrink: 0;
  letter-spacing: 0;
}
.profile-identity { flex: 1; min-width: 0; }
.profile-name {
  font-size: 1rem; font-weight: 700;
  letter-spacing: -0.01em;
  color: var(--ink);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.profile-legal {
  font-size: 0.75rem;
  color: var(--ink-4);
  letter-spacing: 0.02em;
  margin-top: 2px;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.profile-actions { display: flex; gap: 4px; }
.profile-actions .icon-btn { width: 36px; height: 36px; }

.profile-rows { display: flex; flex-direction: column; }
.profile-rows > div {
  display: flex; justify-content: space-between; align-items: center;
  gap: 10px;
  padding: 8px 0;
  border-top: 1px solid var(--line-soft);
}
.profile-rows > div:first-child { border-top: none; }
.profile-rows dt {
  font-family: var(--font-mono);
  font-size: 0.6875rem; font-weight: 600;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--ink-4);
  flex-shrink: 0;
}
.profile-rows dd {
  font-size: 0.8125rem;
  font-weight: 500;
  color: var(--ink);
  text-align: right;
  min-width: 0;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.profile-rows dd.is-empty { color: var(--ink-4); font-style: italic; font-weight: 400; }

.req { color: var(--signal); font-weight: 700; }

.fade-enter-active, .fade-leave-active { transition: opacity 0.15s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
