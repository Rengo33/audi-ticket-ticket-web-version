import { defineStore } from 'pinia';
import { ref } from 'vue';
import { api } from './api';

export const useScheduledStore = defineStore('scheduled', () => {
  const scheduled = ref([]);
  const loading = ref(false);
  const error = ref(null);

  async function fetchScheduled() {
    loading.value = true;
    error.value = null;
    try {
      scheduled.value = await api.get('/api/games/scheduled');
    } catch (e) {
      error.value = e.message || 'Failed to fetch scheduled tasks';
    } finally {
      loading.value = false;
    }
  }

  async function cancelScheduled(id) {
    try {
      await api.delete(`/api/games/scheduled/${id}`);
      scheduled.value = scheduled.value.filter(s => s.id !== id);
    } catch (e) {
      error.value = e.message || 'Failed to cancel scheduled task';
    }
  }

  return { scheduled, loading, error, fetchScheduled, cancelScheduled };
});
