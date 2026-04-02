import { ref } from 'vue'

const MAX_LOGS = 200
const logs = ref([])

export function useLogStore() {
  function addLog(entry) {
    logs.value.unshift(entry)
    if (logs.value.length > MAX_LOGS) {
      logs.value.length = MAX_LOGS
    }
  }

  function clear() {
    logs.value = []
  }

  return { logs, addLog, clear }
}
