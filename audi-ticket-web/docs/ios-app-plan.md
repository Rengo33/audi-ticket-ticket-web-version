# iOS App Integration & Push Notification Plan

## 0. Decision: Push Notification Approach

| Option | Pros | Cons |
|--------|------|------|
| **A. Firebase (FCM)** | Industry standard, handles retries | Requires Google account, credentials file, SDK |
| **B. APNs Direct** | Native iOS, no middleman | Requires Apple Developer cert management |
| **C. Polling + Local Notification** | Zero backend changes, simple | Slight delay (5-10s), battery usage |

**Recommendation**: Start with **Option C (Polling)** for MVP. Add Firebase later if needed.

---

## 1. Backend Updates

### A. Auth Token Expiry
- **Current**: 24 hours (annoying for mobile).
- **Change**: Extend to 30 days in `backend/app/auth.py`.

### B. New API Endpoint
- `GET /api/carts`: Returns active cart sessions for checkout deep linking.

### C. Future (Firebase)
- Add `firebase-admin` to requirements.
- Create `DeviceToken` model.
- Add `POST /api/notifications/register` endpoint.
- Hook into monitor to send push on cart success.

---

## 2. iOS App Architecture

### A. Authentication (`AuthManager.swift`)
- **Key Feature**: User enters password only once.
- **Storage**: Use **iOS Keychain** to store `X-Auth-Token` securely.
- **State Management**: `ObservableObject` with `@Published var isAuthenticated`.
- **Auto-Logout**: Intercept 401 responses to clear Keychain and reset state.

### B. Task Monitoring (`TaskMonitor.swift`)
- **Polling Strategy**: Every 5 seconds, call `GET /api/tasks`.
- **Local Notification**: When any task status changes to `success`, trigger local notification.
- Runs in background using `BGAppRefreshTask` (limited intervals when app closed).

### C. Views
- `LoginView.swift`: Simple password field + "Remember me" (Keychain).
- `TasksView.swift`: List of tasks with status indicators.
- `CartsView.swift`: List of active carts with "Open Checkout" button.
- `ContentView.swift`: Tab-based navigation (Tasks | Carts).

### D. Workflow
1. **Login**: Password → API → Token → Keychain → Main App.
2. **Restart**: App Launch → Keychain Check → Main App (skip login).
3. **Cart Success**: Polling detects `success` → Local Notification → Tap → Open Carts Tab → Safari checkout.

---

## 3. Implementation Order

1. [ ] Extend auth token expiry to 30 days
2. [ ] Add `GET /api/carts` endpoint  
3. [ ] Create iOS Xcode project structure
4. [ ] Implement AuthManager + Keychain
5. [ ] Implement TasksView with polling
6. [ ] Implement CartsView with checkout button
7. [ ] Add local notification on cart success
8. [ ] *(Future)* Add Firebase push notifications

---

## 4. File Structure (iOS App)

```
ios-app/
├── AudiTicketBot.xcodeproj
├── AudiTicketBot/
│   ├── AudiTicketBotApp.swift      # App entry point
│   ├── ContentView.swift            # Tab navigation
│   ├── Models/
│   │   ├── Task.swift
│   │   └── Cart.swift
│   ├── Services/
│   │   ├── APIService.swift         # Network calls
│   │   ├── AuthManager.swift        # Token + Keychain
│   │   ├── KeychainHelper.swift     # Keychain wrapper
│   │   └── TaskMonitor.swift        # Polling + notifications
│   └── Views/
│       ├── LoginView.swift
│       ├── TasksView.swift
│       └── CartsView.swift
└── Info.plist
```
