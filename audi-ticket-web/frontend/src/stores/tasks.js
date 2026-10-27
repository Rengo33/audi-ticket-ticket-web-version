import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from './api'

export const useTaskStore = defineStore('tasks', () => {
  const tasks = ref([])
  const loading = ref(false)
  const error = ref(null)
  
  async function fetchTasks() {
    loading.value = true
    error.value = null
    
    try {
      const response = await api.get('/api/tasks')
      tasks.value = response.tasks || []
    } catch (e) {
      error.value = 'Fehler beim Laden der Tasks'
    } finally {
      loading.value = false
    }
  }
  
  async function createTask(taskData) {
    loading.value = true
    error.value = null
    
    try {
      const response = await api.post('/api/tasks', taskData)
      tasks.value.unshift(response)
      return response
    } catch (e) {
      error.value = e.message || 'Fehler beim Erstellen'
      return null
    } finally {
      loading.value = false
    }
  }
  
  // Optimistic: flip the card at once and lock its buttons; the server's
  // task_update over the WebSocket confirms. Refetch only on failure.
  async function act(taskId, status, call) {
    const task = tasks.value.find(t => t.id === taskId)
    if (task) { task.status = status; task.pending = true }
    try {
      await call()
      return true
    } catch (e) {
      error.value = e.message
      await fetchTasks()
      return false
    } finally {
      if (task) task.pending = false
    }
  }

  const startTask = (taskId) => act(taskId, 'running', () => api.post(`/api/tasks/${taskId}/start`))
  const stopTask = (taskId) => act(taskId, 'stopped', () => api.post(`/api/tasks/${taskId}/stop`))

  async function deleteTask(taskId) {
    const prev = tasks.value
    tasks.value = prev.filter(t => t.id !== taskId)
    try {
      await api.delete(`/api/tasks/${taskId}`)
      return true
    } catch (e) {
      tasks.value = prev
      error.value = e.message
      return false
    }
  }

  function updateTask(taskId, updates) {
    const task = tasks.value.find(t => t.id === taskId)
    if (!task) return
    let changed = false
    for (const key in updates) {
      if (task[key] !== updates[key]) {
        task[key] = updates[key]
        changed = true
      }
    }
    return changed
  }
  
  return {
    tasks,
    loading,
    error,
    fetchTasks,
    createTask,
    startTask,
    stopTask,
    deleteTask,
    updateTask
  }
})
