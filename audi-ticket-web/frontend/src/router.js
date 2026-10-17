import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from './stores/auth'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('./views/Login.vue')
  },
  {
    path: '/',
    name: 'Tasks',
    component: () => import('./views/Tasks.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/tasks',
    redirect: '/'
  },
  {
    path: '/games',
    redirect: '/'
  },
  {
    path: '/detector',
    name: 'Detector',
    component: () => import('./views/Detector.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/carts',
    name: 'Carts',
    component: () => import('./views/Carts.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/billing',
    name: 'Billing',
    component: () => import('./views/Billing.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/logs',
    name: 'Logs',
    component: () => import('./views/Logs.vue'),
    meta: { requiresAuth: true }
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// Navigation guard
router.beforeEach((to, from, next) => {
  const authStore = useAuthStore()

  if (to.meta.requiresAuth && !authStore.isLoggedIn) {
    // Preserve intended destination (full path + query) so Login can resume it.
    const redirect = to.fullPath && to.fullPath !== '/' ? to.fullPath : undefined
    next(redirect ? { path: '/login', query: { redirect } } : '/login')
  } else if (to.path === '/login' && authStore.isLoggedIn) {
    next('/')
  } else {
    next()
  }
})

export default router
