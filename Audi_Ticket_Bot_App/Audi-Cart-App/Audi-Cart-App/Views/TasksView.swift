import SwiftUI

struct TasksView: View {
    @ObservedObject var taskMonitor = TaskMonitor.shared
    @ObservedObject var authManager = AuthManager.shared
    
    var body: some View {
        NavigationStack {
            Group {
                if taskMonitor.tasks.isEmpty && taskMonitor.errorMessage == nil {
                    ContentUnavailableView(
                        "No Tasks",
                        systemImage: "list.bullet.rectangle",
                        description: Text("Create tasks in the web dashboard")
                    )
                } else {
                    List {
                        if let error = taskMonitor.errorMessage {
                            Section {
                                HStack {
                                    Image(systemName: "exclamationmark.triangle.fill")
                                        .foregroundColor(.orange)
                                    Text(error)
                                        .font(.caption)
                                }
                            }
                        }
                        
                        ForEach(taskMonitor.tasks) { task in
                            TaskRowView(task: task)
                        }
                    }
                    .refreshable {
                        await taskMonitor.fetchTasks()
                    }
                }
            }
            .navigationTitle("Tasks")
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button(action: { authManager.logout() }) {
                        Image(systemName: "rectangle.portrait.and.arrow.right")
                    }
                }
            }
        }
    }
}

struct TaskRowView: View {
    let task: TaskItem
    @ObservedObject var taskMonitor = TaskMonitor.shared
    
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text(task.eventName)
                    .font(.headline)
                    .lineLimit(2)
                
                Spacer()
                
                StatusBadge(status: task.status)
            }
            
            Text(task.eventUrl)
                .font(.caption)
                .foregroundColor(.secondary)
                .lineLimit(1)
            
            HStack {
                if task.status == .running {
                    Button("Stop") {
                        Task {
                            await taskMonitor.stopTask(task)
                        }
                    }
                    .buttonStyle(.bordered)
                    .tint(.red)
                } else if task.status == .stopped || task.status == .failed {
                    Button("Start") {
                        Task {
                            await taskMonitor.startTask(task)
                        }
                    }
                    .buttonStyle(.bordered)
                    .tint(.green)
                }
                
                Spacer()
                
                if let cartUrl = task.cartUrl, task.status == .success {
                    Button("Open Cart") {
                        if let url = URL(string: cartUrl) {
                            UIApplication.shared.open(url)
                        }
                    }
                    .buttonStyle(.borderedProminent)
                }
            }
        }
        .padding(.vertical, 4)
    }
}

struct StatusBadge: View {
    let status: TaskStatus
    
    var body: some View {
        Text(status.displayName)
            .font(.caption)
            .fontWeight(.medium)
            .padding(.horizontal, 8)
            .padding(.vertical, 4)
            .background(backgroundColor)
            .foregroundColor(.white)
            .cornerRadius(8)
    }
    
    private var backgroundColor: Color {
        switch status {
        case .running: return .blue
        case .success: return .green
        case .failed: return .red
        case .stopped: return .gray
        case .pending: return .orange
        }
    }
}

#Preview {
    TasksView()
}
