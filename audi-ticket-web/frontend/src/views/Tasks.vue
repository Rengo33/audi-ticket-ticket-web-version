<template>
  <div class="tasks-view">
    <div class="toolbar">
      <button @click="showModal = true" class="primary-btn">+ New Task</button>
    </div>

    <div class="tasks-grid">
      <div v-for="task in taskStore.tasks" :key="task.id" class="task-card">
        <div class="card-header">
          <div class="status-badge" :class="task.status">
            {{ task.status }}
            <span v-if="task.status === 'running'" class="pulse"></span>
          </div>
          <span class="task-id">#{{ task.id }}</span>
        </div>

        <div class="card-body">
          <h3>{{ getDisplayName(task.product_url) }}</h3>
          
          <div class="stats-grid">
            <div class="stat">
              <span class="label">Config</span>
              <span class="value">{{ task.quantity }}tix / {{ task.num_threads }}thr</span>
            </div>
            <div class="stat">
              <span class="label">Scans</span>
              <span class="value">{{ task.scan_count || 0 }}</span>
            </div>
            <div class="stat full-width">
              <span class="label">Status</span>
              <span class="value status-text" :class="{
                'avail': (task.tickets_available || 0) > 0,
                'waiting': (task.tickets_available || 0) <= 0
              }">
                {{ (task.tickets_available || 0) > 0 ? `${task.tickets_available} Tickets Available` : 'Waiting for Release' }}
              </span>
            </div>
          </div>
        </div>

        <div class="card-footer">
          <button v-if="task.status !== 'running'" @click="taskStore.startTask(task.id)" class="icon-btn play">
            ▶
          </button>
          <button v-else @click="taskStore.stopTask(task.id)" class="icon-btn stop">
            ⏹
          </button>
          <button @click="taskStore.deleteTask(task.id)" class="icon-btn delete">
            🗑
          </button>
        </div>
      </div>
    </div>

    <!-- Simple Modal for Creation -->
    <div v-if="showModal" class="modal-overlay" @click.self="showModal = false">
      <div class="modal">
        <h3>Create Task</h3>
        <div class="form-group">
            <label>Product URL</label>
            <input v-model="newTask.url" placeholder="https://..." class="w-full">
        </div>
        <div class="form-row">
            <div class="form-group">
                <label>Quantity</label>
                <input v-model="newTask.quantity" type="number" min="1">
            </div>
            <div class="form-group">
                <label>Threads</label>
                <input v-model="newTask.num_threads" type="number" min="1">
            </div>
        </div>
        
        <div class="modal-actions">
            <button @click="showModal = false" class="cancel-btn">Cancel</button>
            <button @click="createTask" class="create-btn">Create Task</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import { useTaskStore } from '../stores/tasks';

const taskStore = useTaskStore();
const showModal = ref(false);
const newTask = ref({ url: '', quantity: 2, num_threads: 2 });

const getDisplayName = (url) => {
    try {
        const parts = url.split('/');
        return parts[parts.length - 1].replace(/-/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
    } catch { return url; }
};

const createTask = async () => {
    if (!newTask.value.url) return;
    
    await taskStore.createTask({
        product_url: newTask.value.url,
        quantity: parseInt(newTask.value.quantity),
        num_threads: parseInt(newTask.value.num_threads)
    });
    
    showModal.value = false;
    newTask.value = { url: '', quantity: 2, num_threads: 2 };
};

onMounted(() => {
    taskStore.fetchTasks();
});
</script>

<style scoped>
.form-group label {
  display: block;
  font-size: 1.08rem;
  font-weight: 700;
  margin-bottom: 0.5rem;
  color: #181818;
  letter-spacing: 0.01em;
}
.form-group input {
  width: 100%;
  padding: 15px;
  border: 2px solid #b0b0b0;
  border-radius: 10px;
  font-size: 1.12rem;
  color: #181818;
  background: #fff;
  font-weight: 600;
}
.label {
  font-size: 1.02rem;
  color: #222;
  font-weight: 700;
  text-transform: none;
  letter-spacing: 0.01em;
  margin-bottom: 2px;
}
.value {
  font-size: 1.12rem;
  font-weight: 700;
  color: #181818;
  font-variant-numeric: tabular-nums;
}
.card-body h3 {
  font-size: 1.22rem;
  font-weight: 800;
  margin-bottom: 1rem;
  line-height: 1.4;
  color: #181818;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  height: 3em;
}
/* Modal */
.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; backdrop-filter: blur(5px); z-index: 100; }
.modal { background: white; padding: 2rem; border-radius: 20px; width: 100%; max-width: 500px; box-shadow: 0 20px 40px rgba(0,0,0,0.2); }
.modal h3 { font-size: 1.5rem; font-weight: 700; margin-bottom: 1.5rem; }

.form-group { margin-bottom: 1rem; }
.form-group label { display: block; font-size: 0.9rem; font-weight: 600; margin-bottom: 0.5rem; }
.form-group input { width: 100%; padding: 12px; border: 1px solid #e5e5ea; border-radius: 10px; font-size: 1rem; }
.form-row { display: flex; gap: 1rem; }
.form-row .form-group { flex: 1; }

.modal-actions { display: flex; justify-content: flex-end; gap: 1rem; margin-top: 2rem; }
.cancel-btn { background: #f2f2f7; color: black; border: none; padding: 12px 20px; border-radius: 10px; font-weight: 600; cursor: pointer; }
.create-btn { background: #000; color: white; border: none; padding: 12px 20px; border-radius: 10px; font-weight: 600; cursor: pointer; }
</style>
