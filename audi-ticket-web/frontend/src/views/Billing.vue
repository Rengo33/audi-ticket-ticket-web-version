<template>
  <div class="billing-view">
    <div class="toolbar">
      <button @click="showModal = true" class="primary-btn">+ New Profile</button>
    </div>

    <div v-if="profiles.length === 0" class="empty-state">
      <div class="empty-icon">👤</div>
      <h3>No Billing Profiles</h3>
      <p>Create a profile to enable Auto Checkout.</p>
    </div>

    <div v-else class="profiles-grid">
      <div v-for="p in profiles" :key="p.id" class="profile-card">
        <div class="card-header">
          <h3>{{ p.name }}</h3>
          <div class="card-actions-top">
            <button @click="editProfile(p)" class="icon-btn edit">✏️</button>
            <button @click="deleteProfile(p.id)" class="icon-btn delete">🗑</button>
          </div>
        </div>
        <div class="card-body">
          <div class="info-row"><span class="label">Name</span><span>{{ p.firstname }} {{ p.lastname }}</span></div>
          <div class="info-row"><span class="label">Email</span><span>{{ p.email }}</span></div>
          <div class="info-row"><span class="label">Stammnr.</span><span>{{ p.stammnummer }}</span></div>
          <div class="info-row"><span class="label">Karte</span><span>{{ p.has_card ? '•••• ' + p.card_last4 : 'Keine' }}</span></div>
          <div class="info-row"><span class="label">Rechnung</span><span>{{ p.invoice_street ? p.invoice_street + ', ' + p.invoice_city : 'Nicht gesetzt' }}</span></div>
        </div>
      </div>
    </div>

    <!-- Modal -->
    <div v-if="showModal" class="modal-overlay" @click.self="closeModal">
      <div class="modal">
        <h3>{{ editingId ? 'Profil bearbeiten' : 'Neues Profil' }}</h3>

        <div class="form-section">
          <h4>Profil</h4>
          <div class="form-group">
            <label>Profilname</label>
            <input v-model="form.name" placeholder="z.B. Leon, Mate">
          </div>
        </div>

        <div class="form-section">
          <h4>Persönliche Daten</h4>
          <div class="form-row">
            <div class="form-group"><label>Vorname</label><input v-model="form.firstname"></div>
            <div class="form-group"><label>Nachname</label><input v-model="form.lastname"></div>
          </div>
          <div class="form-group"><label>Email</label><input v-model="form.email" type="email"></div>
          <div class="form-group"><label>Telefon</label><input v-model="form.telephone"></div>
          <div class="form-row">
            <div class="form-group"><label>Stammnummer</label><input v-model="form.stammnummer"></div>
            <div class="form-group"><label>Abteilung</label><input v-model="form.department" placeholder="Optional"></div>
          </div>
        </div>

        <div class="form-section">
          <h4>Rechnungsadresse</h4>
          <div class="form-group"><label>Empfänger</label><input v-model="form.invoice_recipient" placeholder="Optional, default: Vor- + Nachname"></div>
          <div class="form-row">
            <div class="form-group"><label>Firma</label><input v-model="form.invoice_company" placeholder="Optional"></div>
            <div class="form-group"><label>Steuer-ID</label><input v-model="form.invoice_tax_id" placeholder="Optional"></div>
          </div>
          <div class="form-group"><label>Straße</label><input v-model="form.invoice_street"></div>
          <div class="form-row">
            <div class="form-group"><label>PLZ</label><input v-model="form.invoice_postcode"></div>
            <div class="form-group"><label>Stadt</label><input v-model="form.invoice_city"></div>
          </div>
        </div>

        <div class="form-section">
          <h4>Kartendaten</h4>
          <div class="form-group"><label>Kartennummer</label><input v-model="form.card_number" placeholder="4165 9834 ..." maxlength="19"></div>
          <div class="form-row">
            <div class="form-group"><label>Monat</label><input v-model="form.card_exp_month" placeholder="11" maxlength="2"></div>
            <div class="form-group"><label>Jahr</label><input v-model="form.card_exp_year" placeholder="27" maxlength="2"></div>
            <div class="form-group"><label>CVC</label><input v-model="form.card_cvc" placeholder="123" maxlength="4" type="password"></div>
          </div>
        </div>

        <div class="modal-actions">
          <button @click="closeModal" class="cancel-btn">Abbrechen</button>
          <button @click="saveProfile" class="create-btn" :disabled="saving">{{ saving ? 'Speichern...' : 'Speichern' }}</button>
        </div>
      </div>
    </div>
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

const fetchProfiles = async () => {
  try {
    profiles.value = await api.get('/api/billing/profiles');
  } catch { /* ignore */ }
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
    alert('Bitte alle Pflichtfelder ausfüllen (Name, Vorname, Nachname, Email, Stammnummer)');
    return;
  }
  saving.value = true;
  try {
    if (editingId.value) {
      await api.request('PUT', `/api/billing/profiles/${editingId.value}`, form.value);
    } else {
      await api.post('/api/billing/profiles', form.value);
    }
    await fetchProfiles();
    closeModal();
  } catch (e) {
    alert('Fehler: ' + (e.message || 'Unknown'));
  } finally {
    saving.value = false;
  }
};

const deleteProfile = async (id) => {
  if (!confirm('Profil löschen?')) return;
  try {
    await api.delete(`/api/billing/profiles/${id}`);
    profiles.value = profiles.value.filter(p => p.id !== id);
  } catch (e) {
    alert('Fehler: ' + (e.message || 'Unknown'));
  }
};

onMounted(fetchProfiles);
</script>

<style scoped>
.billing-view { padding: 0; }
.toolbar { margin-bottom: 2rem; display: flex; justify-content: flex-end; }
.primary-btn { background: var(--btn-primary-bg); color: var(--btn-primary-text); padding: 12px 24px; border-radius: 12px; font-weight: 600; cursor: pointer; border: none; }

.profiles-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr)); gap: 1.5rem; }

.profile-card { background: var(--card-bg); border-radius: 16px; padding: 1.5rem; border: 1px solid var(--border-light); }
.card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; }
.card-header h3 { font-size: 1.2rem; font-weight: 700; }
.card-actions-top { display: flex; gap: 4px; }
.icon-btn { width: 36px; height: 36px; border-radius: 8px; border: none; cursor: pointer; font-size: 0.9rem; display: flex; align-items: center; justify-content: center; }
.icon-btn.edit { background: rgba(0,122,255,0.1); }
.icon-btn.delete { background: rgba(255,59,48,0.1); }

.info-row { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid var(--border-light); font-size: 0.9rem; }
.info-row .label { color: var(--text-tertiary); }

.empty-state { text-align: center; padding: 4rem; color: var(--text-tertiary); }
.empty-icon { font-size: 3rem; margin-bottom: 1rem; }

.modal-overlay { position: fixed; inset: 0; background: var(--modal-overlay); display: flex; align-items: center; justify-content: center; backdrop-filter: blur(5px); z-index: 100; }
.modal { background: var(--card-bg); padding: 2rem; border-radius: 20px; width: 100%; max-width: 550px; max-height: 90vh; overflow-y: auto; }
.modal h3 { font-size: 1.5rem; font-weight: 700; margin-bottom: 1.5rem; }

.form-section { margin-bottom: 1.5rem; }
.form-section h4 { font-size: 0.85rem; font-weight: 700; color: var(--text-tertiary); text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 0.75rem; }
.form-group { margin-bottom: 0.75rem; }
.form-group label { display: block; font-size: 0.85rem; font-weight: 600; margin-bottom: 0.3rem; }
.form-group input { width: 100%; padding: 10px; border: 1px solid var(--border-light); border-radius: 8px; font-size: 0.95rem; background: var(--input-bg); color: var(--text-primary); }
.form-row { display: flex; gap: 0.75rem; }
.form-row .form-group { flex: 1; }

.modal-actions { display: flex; justify-content: flex-end; gap: 1rem; margin-top: 1.5rem; }
.cancel-btn { background: var(--hover-bg); color: var(--text-primary); border: none; padding: 12px 20px; border-radius: 10px; font-weight: 600; cursor: pointer; }
.create-btn { background: var(--btn-primary-bg); color: var(--btn-primary-text); border: none; padding: 12px 20px; border-radius: 10px; font-weight: 600; cursor: pointer; }

@media (max-width: 768px) {
  .profiles-grid { grid-template-columns: 1fr; }
  .modal { max-width: 95vw; padding: 1.5rem; }
  .form-row { flex-direction: column; gap: 0; }
}
</style>
