import SwiftUI

struct SettingsView: View {
    @ObservedObject var authManager = AuthManager.shared
    @ObservedObject var taskMonitor = TaskMonitor.shared
    
    @State private var showLogoutConfirmation = false
    
    var body: some View {
        NavigationStack {
            List {
                // Account Section
                Section {
                    HStack {
                        Image(systemName: "person.circle.fill")
                            .font(.largeTitle)
                            .foregroundColor(.blue)
                        
                        VStack(alignment: .leading) {
                            Text("Authenticated")
                                .font(.headline)
                            Text("Token stored in Keychain")
                                .font(.caption)
                                .foregroundColor(.secondary)
                        }
                    }
                    .padding(.vertical, 4)
                } header: {
                    Text("Account")
                }
                
                // Server Section
                Section {
                    HStack {
                        Text("Server")
                        Spacer()
                        Text(APIService.shared.baseURL)
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                    
                    HStack {
                        Text("Tasks")
                        Spacer()
                        Text("\(taskMonitor.tasks.count)")
                            .foregroundColor(.secondary)
                    }
                    
                    HStack {
                        Text("Active Carts")
                        Spacer()
                        Text("\(taskMonitor.carts.count)")
                            .foregroundColor(.secondary)
                    }
                } header: {
                    Text("Status")
                }
                
                // Polling Section
                Section {
                    HStack {
                        Text("Polling Interval")
                        Spacer()
                        Text("5 seconds")
                            .foregroundColor(.secondary)
                    }
                    
                    HStack {
                        Image(systemName: "bell.badge.fill")
                            .foregroundColor(.orange)
                        Text("Notifications")
                        Spacer()
                        Text("Enabled")
                            .foregroundColor(.green)
                    }
                } header: {
                    Text("Monitoring")
                } footer: {
                    Text("The app polls the server every 5 seconds and sends a notification when a cart is successfully created.")
                }
                
                // App Info Section
                Section {
                    HStack {
                        Text("Version")
                        Spacer()
                        Text("1.0.0")
                            .foregroundColor(.secondary)
                    }
                    
                    HStack {
                        Text("Build")
                        Spacer()
                        Text("1")
                            .foregroundColor(.secondary)
                    }
                } header: {
                    Text("App Info")
                }
                
                // Danger Zone
                Section {
                    Button(action: {
                        showLogoutConfirmation = true
                    }) {
                        HStack {
                            Image(systemName: "rectangle.portrait.and.arrow.right")
                                .foregroundColor(.red)
                            Text("Logout")
                                .foregroundColor(.red)
                        }
                    }
                } header: {
                    Text("Account Actions")
                } footer: {
                    Text("Logging out will remove your authentication token from this device.")
                }
            }
            .navigationTitle("Settings")
            .confirmationDialog(
                "Logout?",
                isPresented: $showLogoutConfirmation,
                titleVisibility: .visible
            ) {
                Button("Logout", role: .destructive) {
                    taskMonitor.stopPolling()
                    authManager.logout()
                }
                Button("Cancel", role: .cancel) {}
            } message: {
                Text("You will need to enter your password again to use the app.")
            }
        }
    }
}

#Preview {
    SettingsView()
}
