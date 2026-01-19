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
  
  async function startTask(taskId) {
    try {
      await api.post(`/api/tasks/${taskId}/start`)
      await fetchTasks()
      return true
    } catch (e) {
      error.value = e.message
      return false
    }
  }
  
  async function stopTask(taskId) {
    try {
      await api.post(`/api/tasks/${taskId}/stop`)
      await fetchTasks()
      return true
    } catch (e) {
      // Even on error, refresh tasks to sync state with backend
      await fetchTasks()
      error.value = e.message
      return false
    }
  }
  
  async function deleteTask(taskId) {
    try {
      await api.delete(`/api/tasks/${taskId}`)
      tasks.value = tasks.value.filter(t => t.id !== taskId)
      return true
    } catch (e) {
      // Even on error, refresh tasks to sync state
      await fetchTasks()
      error.value = e.message
      return false
    }
  }
  
  function updateTask(taskId, updates) {
    const index = tasks.value.findIndex(t => t.id === taskId)
    if (index !== -1) {
      tasks.value[index] = { ...tasks.value[index], ...updates }
    }
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
