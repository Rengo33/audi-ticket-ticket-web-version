import SwiftUI

struct TasksView: View {
    @ObservedObject var taskMonitor = TaskMonitor.shared
    @ObservedObject var authManager = AuthManager.shared
    @State private var showCreateTask = false
    @State private var showDeleteAllConfirmation = false
    
    var body: some View {
        NavigationStack {
            ZStack {
                Color(uiColor: .systemGroupedBackground)
                    .ignoresSafeArea()
                
                if taskMonitor.tasks.isEmpty && taskMonitor.errorMessage == nil {
                    ContentUnavailableView {
                        Label("No Tasks", systemImage: "list.bullet.rectangle.portrait")
                    } description: {
                        Text("Create a task to start monitoring tickets.")
                    } actions: {
                        Button("Create Task") {
                            showCreateTask = true
                        }
                        .buttonStyle(.borderedProminent)
                        .controlSize(.regular)
                    }
                } else {
                    List {
                        if let error = taskMonitor.errorMessage {
                            Section {
                                HStack {
                                    Image(systemName: "exclamationmark.triangle.fill")
                                        .foregroundColor(.orange)
                                    Text(error)
                                        .font(.subheadline)
                                }
                            }
                        }
                        
                        ForEach(taskMonitor.tasks) { task in
                            ZStack {
                                NavigationLink(destination: TaskDetailView(task: task)) {
                                    EmptyView()
                                }
                                .opacity(0)
                                
                                TaskRowView(task: task)
                            }
                            .listRowInsets(EdgeInsets(top: 8, leading: 16, bottom: 8, trailing: 16))
                            .listRowSeparator(.hidden)
                            .listRowBackground(Color.clear)
                        }
                        .onDelete(perform: deleteTasks)
                    }
                    .listStyle(.plain)
                    .refreshable {
                        await taskMonitor.fetchTasks()
                    }
                }
            }
            .navigationTitle("Tasks")
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    if !taskMonitor.tasks.isEmpty {
                        Button(action: { showDeleteAllConfirmation = true }) {
                            Image(systemName: "trash")
                                .foregroundColor(.red)
                        }
                    }
                }
                
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button(action: { showCreateTask = true }) {
                        Image(systemName: "plus.circle.fill")
                            .symbolRenderingMode(.hierarchical)
                            .font(.system(size: 28))
                            .foregroundColor(.primary)
                    }
                }
            }
            .sheet(isPresented: $showCreateTask) {
                CreateTaskView()
            }
            .confirmationDialog(
                "Delete All Tasks?",
                isPresented: $showDeleteAllConfirmation,
                titleVisibility: .visible
            ) {
                Button("Delete All", role: .destructive) {
                    Task {
                        await taskMonitor.deleteAllTasks()
                    }
                }
                Button("Cancel", role: .cancel) {}
            } message: {
                Text("This will permanently remove all tasks. This action cannot be undone.")
            }
        }
    }
    
    private func deleteTasks(at offsets: IndexSet) {
        for index in offsets {
            let task = taskMonitor.tasks[index]
            Task {
                await taskMonitor.deleteTask(task)
            }
        }
    }
}

struct TaskRowView: View {
    let task: TaskItem
    @ObservedObject var taskMonitor = TaskMonitor.shared
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            // Header: Status and Title
            HStack(alignment: .center, spacing: 12) {
                StatusIndicator(status: task.status)
                
                VStack(alignment: .leading, spacing: 2) {
                    Text(task.displayName)
                        .font(.system(size: 16, weight: .semibold))
                        .foregroundColor(.primary)
                        .lineLimit(1)
                    
                    Text(task.status.displayName)
                        .font(.system(size: 12, weight: .medium))
                        .foregroundColor(.secondary)
                }
                
                Spacer()
                
                // Action Button
                actionButton
            }
            
            Divider()
                .opacity(0.5)
            
            // Stats Row
            HStack {
                Label {
                    Text("\(task.quantity) Tickets")
                } icon: {
                    Image(systemName: "ticket")
                }
                .font(.system(size: 13, weight: .medium))
                .foregroundColor(.secondary)
                
                Spacer()
                
                if task.status == .running {
                    // Show availability status
                    Label {
                        Text(task.ticketsAvailable > 0 ? "\(task.ticketsAvailable) available" : "No tickets")
                    } icon: {
                        Image(systemName: task.ticketsAvailable > 0 ? "checkmark.circle" : "xmark.circle")
                    }
                    .font(.system(size: 13, weight: .medium))
                    .foregroundColor(task.ticketsAvailable > 0 ? .green : .orange)
                    
                    Spacer()
                    
                    Label {
                        Text("\(task.scanCount)")
                    } icon: {
                        Image(systemName: "arrow.triangle.2.circlepath")
                    }
                    .font(.system(size: 13, weight: .medium))
                    .foregroundColor(.secondary)
                } else {
                    Label {
                        Text("\(task.numThreads) Threads")
                    } icon: {
                        Image(systemName: "cpu")
                    }
                    .font(.system(size: 13, weight: .medium))
                    .foregroundColor(.secondary)
                }
            }
        }
        .padding(16)
        .background(Color(uiColor: .secondarySystemGroupedBackground))
        .cornerRadius(16)
        .shadow(color: Color.black.opacity(0.05), radius: 5, x: 0, y: 2)
    }
    
    @ViewBuilder
    private var actionButton: some View {
        if task.status == .running {
            Button(action: {
                Task { await taskMonitor.stopTask(task) }
            }) {
                Image(systemName: "stop.circle.fill")
                    .font(.system(size: 28))
                    .foregroundColor(.orange)
                    .symbolRenderingMode(.hierarchical)
            }
            .buttonStyle(.plain)
        } else if task.status == .stopped || task.status == .failed || task.status == .pending {
            Button(action: {
                Task { await taskMonitor.startTask(task) }
            }) {
                Image(systemName: "play.circle.fill")
                    .font(.system(size: 28))
                    .foregroundColor(.primary)
                    .symbolRenderingMode(.hierarchical)
            }
            .buttonStyle(.plain)
        } else if task.status == .success, let token = task.cartToken {
            Button(action: {
                openCheckout(token: token)
            }) {
                Image(systemName: "cart.circle.fill")
                    .font(.system(size: 28))
                    .foregroundColor(.green)
                    .symbolRenderingMode(.hierarchical)
            }
            .buttonStyle(.plain)
        }
    }
    
    private func openCheckout(token: String) {
        let urlString = "\(APIService.shared.baseURL.replacingOccurrences(of: "/api", with: ""))/checkout/\(token)/cart"
        if let url = URL(string: urlString) {
            UIApplication.shared.open(url)
        }
    }
}

struct StatusIndicator: View {
    let status: TaskStatus
    
    var color: Color {
        switch status {
        case .running: return .blue
        case .success: return .green
        case .failed: return .red
        case .stopped: return .gray
        case .pending: return .orange
        }
    }
    
    var body: some View {
        ZStack {
            if status == .running {
                Circle()
                    .stroke(color.opacity(0.2), lineWidth: 4)
                    .frame(width: 12, height: 12)
            }
            
            Circle()
                .fill(color)
                .frame(width: 8, height: 8)
                .shadow(color: color.opacity(0.5), radius: 4, x: 0, y: 0)
        }
        .frame(width: 16, height: 16)
    }
}

#Preview {
    TasksView()
}
