# Frontend Development Guide

## Current Focus Areas
- Enhance mobile responsiveness
- Improve WebSocket reconnection logic
- Better loading states and error handling
- Optimize real-time updates performance

## Key Dependencies
- **Vue 3** - Progressive framework with Composition API
- **Vite** - Build tool and dev server
- **Pinia** - State management
- **TailwindCSS** - Utility-first styling
- **Axios** - HTTP client

## Code Structure
```
frontend/
├── src/
│   ├── main.js           # App entry point
│   ├── App.vue           # Root component
│   ├── router/           # Vue Router config
│   │   └── index.js
│   ├── stores/           # Pinia stores (STATE MANAGEMENT)
│   │   ├── auth.js       # Authentication state
│   │   ├── tasks.js      # Task management
│   │   ├── cart.js       # Cart sessions
│   │   └── api.js        # API client wrapper
│   ├── views/            # Page components
│   │   ├── Dashboard.vue
│   │   ├── Tasks.vue
│   │   ├── Carts.vue
│   │   ├── Games.vue
│   │   └── Login.vue
│   ├── components/       # Reusable components
│   └── assets/           # Static assets
├── public/               # Public static files
└── index.html           # Entry HTML
```

## Architecture Patterns

### State Management (Pinia)
**Convention**: Use Composition API style for all stores
```javascript
// stores/example.js
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useExampleStore = defineStore('example', () => {
  // State
  const data = ref([])
  
  // Getters
  const filteredData = computed(() => data.value.filter(...))
  
  // Actions
  async function fetchData() {
    // async logic
  }
  
  return { data, filteredData, fetchData }
})
```

### Component Patterns
**Use Composition API** for all components:
```vue
<script setup>
import { ref, onMounted } from 'vue'
import { useTasksStore } from '@/stores/tasks'

const tasksStore = useTasksStore()
const localState = ref(null)

onMounted(() => {
  tasksStore.fetchTasks()
})
</script>
```

## Critical Store Logic

### auth.js
**Purpose**: Manages authentication state and JWT tokens
**Key State**:
- `token` - JWT access token (stored in localStorage)
- `isAuthenticated` - Computed boolean

**Important**: Token is set in axios defaults on login

### tasks.js
**Purpose**: Task CRUD and WebSocket integration
**Key Methods**:
- `fetchTasks()` - Load all tasks from API
- `createTask(taskData)` - Create new monitoring task
- `updateTask(id, updates)` - Update task status
- `handleWebSocketMessage(msg)` - Process real-time updates

**WebSocket Integration**: Updates task state from `task_update` messages

### cart.js
**Purpose**: Cart session management
**Key Features**:
- Stores successful cart sessions with tokens
- Generates mobile checkout URLs
- Tracks cart expiration (17 minutes)

### api.js
**Purpose**: Axios instance with auth interceptors
**Configuration**:
- Base URL from env variable
- Auto-attaches JWT token to requests
- Handles 401 redirects to login

## WebSocket Connection

### Connection Management
```javascript
// Established in main store or component
const ws = new WebSocket(`ws://${API_BASE}/api/ws`)

ws.onmessage = (event) => {
  const msg = JSON.parse(event.data)
  
  switch(msg.type) {
    case 'task_update':
      // Update task in store
      break
    case 'scan_update':
      // Update scan count
      break
    case 'log':
      // Add to task logs
      break
    case 'cart_success':
      // Show notification, add to cart store
      break
  }
}
```

**Current Issue**: No auto-reconnect on disconnect
**TODO**: Add exponential backoff reconnection logic

## Mobile Checkout Flow

### How It Works
1. Backend successfully carts tickets → generates unique token
2. Frontend receives `cart_success` WebSocket message with token
3. Mobile checkout URL: `/mobile/checkout/{token}`
4. iOS app opens this URL → backend injects session cookie → redirects to checkout

**Critical**: Token is single-use and expires after first access

## Styling Conventions

### TailwindCSS
- Use utility classes directly in templates
- Custom components in `tailwind.config.js` for repeated patterns
- Responsive design: mobile-first approach
```vue
<!-- Good -->
<div class="flex flex-col md:flex-row gap-4 p-4">
  <button class="bg-blue-500 hover:bg-blue-600 text-white px-4 py-2 rounded">
    Action
  </button>
</div>
```

### Color Scheme
- Primary: Blue (#3B82F6)
- Success: Green (#10B981)
- Error: Red (#EF4444)
- Warning: Yellow (#F59E0B)

## Environment Variables

Required in `.env`:
```
VITE_API_URL=http://localhost:8000
```

## Known Issues & Tech Debt
- [ ] WebSocket doesn't auto-reconnect on connection loss
- [ ] No optimistic updates (waits for server confirmation)
- [ ] Loading states are inconsistent across views
- [ ] Error messages not user-friendly
- [ ] No offline detection/handling
- [ ] Cart expiration countdown not visual
- [ ] Mobile nav menu needs improvement
- [ ] No form validation on task creation
- [ ] Accessibility (a11y) not implemented

## Testing Gaps
- [ ] No unit tests for stores
- [ ] No component tests
- [ ] No E2E tests
- [ ] WebSocket mock needed for testing

## When Making Changes

### Adding New Views
1. Create component in `src/views/`
2. Add route in `src/router/index.js`
3. Update navigation if needed
4. Ensure mobile responsive

### Adding New Store
1. Create in `src/stores/`
2. Use Composition API pattern
3. Export with `defineStore`
4. Import and use in components with `useStoreName()`

### Modifying WebSocket Handling
1. Ensure backward compatibility with message types
2. Update both sender (component) and receiver (store)
3. Test real-time updates with backend running
4. Handle connection errors gracefully

### API Integration
1. Use the `api.js` store for axios instance
2. All requests automatically include JWT token
3. Handle errors with try/catch and user feedback
4. Update relevant Pinia store after successful requests

## Performance Considerations
- WebSocket messages can be frequent during active monitoring
- Use `computed` for derived state to avoid re-renders
- Lazy load views with `() => import()`
- Debounce search/filter inputs

## Responsive Design Breakpoints
```javascript
// tailwind.config.js
{
  sm: '640px',   // Small tablets
  md: '768px',   // Tablets
  lg: '1024px',  // Laptops
  xl: '1280px',  // Desktops
}
```

**Mobile-first approach**: Base styles for mobile, add `md:` `lg:` for larger screens

## Common Development Tasks

### Run Dev Server
```bash
cd frontend
npm install
npm run dev
# Opens on http://localhost:3000
```

### Build for Production
```bash
npm run build
# Output in dist/
```

### Preview Production Build
```bash
npm run preview
```

### Add New Dependency
```bash
npm install package-name
```

### Fix ESLint Issues
```bash
npm run lint
```

## API Endpoints Used

### Authentication
- `POST /api/auth/login` - Login with password

### Tasks
- `GET /api/tasks` - List all tasks
- `POST /api/tasks` - Create new task
- `PUT /api/tasks/{id}` - Update task
- `DELETE /api/tasks/{id}` - Delete task
- `POST /api/tasks/{id}/start` - Start monitoring
- `POST /api/tasks/{id}/stop` - Stop monitoring

### Games/Events
- `GET /api/games` - List games
- `POST /api/games` - Create game
- `DELETE /api/games/{id}` - Delete game

### Carts
- `GET /api/carts` - List cart sessions

### WebSocket
- `WS /api/ws` - Real-time updates

## Component Communication

### Parent → Child
Use props:
```vue
<!-- Parent -->
<TaskCard :task="task" @update="handleUpdate" />

<!-- Child -->
<script setup>
defineProps({
  task: Object
})

const emit = defineEmits(['update'])
</script>
```

### Child → Parent
Use emits (shown above)

### Global State
Use Pinia stores (preferred for complex state)

## Next Priority Tasks
1. **WebSocket Reconnection** - Add auto-reconnect with exponential backoff
2. **Loading States** - Consistent loading indicators across all views
3. **Form Validation** - Add validation to task creation form
4. **Error Handling** - Better error messages and user feedback
5. **Mobile UX** - Improve navigation and responsive layout
6. **Cart Countdown** - Visual timer showing cart expiration
