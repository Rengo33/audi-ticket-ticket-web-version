import SwiftUI

struct ContentView: View {
    @ObservedObject var authManager = AuthManager.shared
    @ObservedObject var taskMonitor = TaskMonitor.shared
    @State private var selectedTab = 0
    
    var body: some View {
        Group {
            if authManager.isAuthenticated {
                TabView(selection: $selectedTab) {
                    GamesView()
                        .tabItem {
                            Label("Games", systemImage: "sportscourt.fill")
                        }
                        .tag(0)
                    
                    TasksView()
                        .tabItem {
                            Label("Tasks", systemImage: "list.bullet.clipboard")
                        }
                        .tag(1)
                    
                    CartsView()
                        .tabItem {
                            Label("Carts", systemImage: "cart.fill")
                        }
                        .badge(taskMonitor.carts.filter { !$0.isExpired }.count)
                        .tag(2)
                    
                    SettingsView()
                        .tabItem {
                            Label("Settings", systemImage: "gearshape.fill")
                        }
                        .tag(3)
                }
                .onAppear {
                    taskMonitor.startPolling()
                }
                .onDisappear {
                    taskMonitor.stopPolling()
                }
                .onReceive(NotificationCenter.default.publisher(for: .openCartsTab)) { _ in
                    selectedTab = 2
                }
            } else {
                LoginView()
            }
        }
        .animation(.easeInOut, value: authManager.isAuthenticated)
    }
}

#Preview {
    ContentView()
}
