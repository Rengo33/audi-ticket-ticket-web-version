import { useAuthStore } from './auth'

const BASE_URL = ''

class ApiClient {
  async request(method, url, data = null) {
    const authStore = useAuthStore()
    
    const options = {
      method,
      headers: {
        'Content-Type': 'application/json'
      }
    }
    
    if (authStore.token) {
      options.headers['X-Auth-Token'] = authStore.token
    }
    
    if (data) {
      options.body = JSON.stringify(data)
    }
    
    const response = await fetch(BASE_URL + url, options)
    
    if (response.status === 401) {
      authStore.logout()
      window.location.href = '/login'
      throw new Error('Unauthorized')
    }
    
    const json = await response.json()
    
    if (!response.ok) {
      throw new Error(json.detail || 'Request failed')
    }
    
    return json
  }
  
  get(url) {
    return this.request('GET', url)
  }
  
  post(url, data) {
    return this.request('POST', url, data)
  }
  
  delete(url) {
    return this.request('DELETE', url)
  }
}

export const api = new ApiClient()
