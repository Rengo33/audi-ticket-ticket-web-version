import SwiftUI

struct TaskDetailView: View {
    let task: TaskItem
    @ObservedObject var taskMonitor = TaskMonitor.shared
    @Environment(\.dismiss) private var dismiss
    
    @State private var showDeleteConfirmation = false
    @State private var isDeleting = false
    
    var body: some View {
        ScrollView {
            VStack(spacing: 20) {
                // MARK: - Header Status Card
                VStack(spacing: 16) {
                    HStack {
                        StatusIndicator(status: task.status)
                        Text(task.status.displayName)
                            .font(.headline)
                            .foregroundColor(.secondary)
                        
                        Spacer()
                        
                        Text("#\(task.id)")
                            .font(.system(.body, design: .monospaced))
                            .foregroundColor(.secondary)
                            .padding(.horizontal, 8)
                            .padding(.vertical, 4)
                            .background(Color(uiColor: .tertiarySystemGroupedBackground))
                            .cornerRadius(6)
                    }
                    
                    VStack(alignment: .leading, spacing: 8) {
                        Text(task.displayName)
                            .font(.title3)
                            .fontWeight(.bold)
                            .multilineTextAlignment(.leading)
                        
                        Text(task.productUrl)
                            .font(.caption)
                            .foregroundColor(.blue)
                            .lineLimit(1)
                            .truncationMode(.middle)
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                    
                    if let error = task.errorMessage {
                        HStack(alignment: .top, spacing: 12) {
                            Image(systemName: "exclamationmark.triangle.fill")
                                .foregroundColor(.red)
                            Text(error)
                                .font(.callout)
                                .foregroundColor(.primary)
                                .fixedSize(horizontal: false, vertical: true)
                        }
                        .padding()
                        .background(Color.red.opacity(0.1))
                        .cornerRadius(12)
                    }
                }
                .padding(20)
                .background(Color(uiColor: .secondarySystemGroupedBackground))
                .cornerRadius(20)
                
                // MARK: - Stats Grid
                LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 16) {
                    DetailStatCard(title: "Quantity", value: "\(task.quantity)", icon: "ticket")
                    DetailStatCard(title: "Threads", value: "\(task.numThreads)", icon: "cpu")
                    
                    if task.status == .running {
                        DetailStatCard(title: "Scans", value: "\(task.scanCount)", icon: "arrow.triangle.2.circlepath")
                    }
                }
                
                // MARK: - Timestamps
                VStack(spacing: 0) {
                    DetailRow(label: "Created", value: formatDate(task.createdAt))
                    if let startedAt = task.startedAt {
                        Divider().padding(.leading)
                        DetailRow(label: "Started", value: formatDate(startedAt))
                    }
                    if let completedAt = task.completedAt {
                        Divider().padding(.leading)
                        DetailRow(label: "Completed", value: formatDate(completedAt))
                    }
                }
                .background(Color(uiColor: .secondarySystemGroupedBackground))
                .cornerRadius(16)
                
                // MARK: - Debug Info (IDs)
                if task.eventId != nil || task.ticketId != nil {
                    VStack(spacing: 0) {
                        if let eventId = task.eventId {
                            DetailRow(label: "Event ID", value: eventId, monospaced: true)
                        }
                        if let ticketId = task.ticketId {
                            if task.eventId != nil { Divider().padding(.leading) }
                            DetailRow(label: "Ticket ID", value: ticketId, monospaced: true)
                        }
                    }
                    .background(Color(uiColor: .secondarySystemGroupedBackground))
                    .cornerRadius(16)
                }
                
                // MARK: - Actions
                VStack(spacing: 12) {
                    if task.status == .success, let token = task.cartToken {
                        Button(action: { openCheckout(token: token) }) {
                            HStack {
                                Spacer()
                                Label("Go to Checkout", systemImage: "cart.fill")
                                    .fontWeight(.bold)
                                Spacer()
                            }
                            .padding()
                            .background(Color.green)
                            .foregroundColor(.white)
                            .cornerRadius(14)
                        }
                    }
                    
                    if task.status == .running {
                        Button(action: {
                            Task { await taskMonitor.stopTask(task) }
                        }) {
                            HStack {
                                Spacer()
                                Label("Stop Task", systemImage: "stop.fill")
                                    .fontWeight(.semibold)
                                Spacer()
                            }
                            .padding()
                            .background(Color(uiColor: .secondarySystemGroupedBackground))
                            .foregroundColor(.orange)
                            .cornerRadius(14)
                        }
                    } else if task.status == .stopped || task.status == .failed || task.status == .pending {
                        Button(action: {
                            Task { await taskMonitor.startTask(task) }
                        }) {
                            HStack {
                                Spacer()
                                Label("Start Task", systemImage: "play.fill")
                                    .fontWeight(.semibold)
                                Spacer()
                            }
                            .padding()
                            .background(Color.primary)
                            .foregroundColor(Color(uiColor: .systemBackground))
                            .cornerRadius(14)
                        }
                    }
                    
                    Button(action: { showDeleteConfirmation = true }) {
                        Text("Delete Task")
                            .foregroundColor(.red)
                            .padding()
                    }
                }
                .padding(.top, 20)
            }
            .padding()
        }
        .background(Color(uiColor: .systemGroupedBackground))
        .navigationTitle("Task Details")
        .navigationBarTitleDisplayMode(.inline)
        .confirmationDialog(
            "Delete Task?",
            isPresented: $showDeleteConfirmation,
            titleVisibility: .visible
        ) {
            Button("Delete", role: .destructive) { deleteTask() }
            Button("Cancel", role: .cancel) {}
        } message: {
            Text("This action cannot be undone.")
        }
    }
    
    // MARK: - Helpers
    private func formatDate(_ dateString: String) -> String {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        
        var date = formatter.date(from: dateString)
        if date == nil {
            formatter.formatOptions = [.withInternetDateTime]
            date = formatter.date(from: dateString)
        }
        
        guard let parsedDate = date else { return dateString }
        
        let displayFormatter = DateFormatter()
        displayFormatter.dateStyle = .medium
        displayFormatter.timeStyle = .medium
        
        return displayFormatter.string(from: parsedDate)
    }
    
    private func openCheckout(token: String) {
        let urlString = "\(APIService.shared.baseURL.replacingOccurrences(of: "/api", with: ""))/checkout/\(token)/cart"
        guard let url = URL(string: urlString) else { return }
        UIApplication.shared.open(url)
    }
    
    private func deleteTask() {
        isDeleting = true
        Task {
            await taskMonitor.deleteTask(task)
            await MainActor.run {
                dismiss()
            }
        }
    }
}

// MARK: - Components
struct DetailStatCard: View {
    let title: String
    let value: String
    let icon: String
    
    var body: some View {
        VStack(spacing: 12) {
            Image(systemName: icon)
                .font(.system(size: 20))
                .foregroundColor(.secondary)
            
            VStack(spacing: 4) {
                Text(value)
                    .font(.title2)
                    .fontWeight(.bold)
                    .monospacedDigit()
                
                Text(title)
                    .font(.caption)
                    .foregroundColor(.secondary)
                    .fontWeight(.medium)
            }
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 20)
        .background(Color(uiColor: .secondarySystemGroupedBackground))
        .cornerRadius(16)
    }
}

struct DetailRow: View {
    let label: String
    let value: String
    var monospaced: Bool = false
    
    var body: some View {
        HStack {
            Text(label)
                .foregroundColor(.secondary)
            Spacer()
            Text(value)
                .foregroundColor(.primary)
                .font(monospaced ? .system(.body, design: .monospaced) : .body)
        }
        .padding()
    }
}

#Preview {
    NavigationStack {
        TaskDetailView(task: TaskItem(
            id: 1,
            productUrl: "https://audidefuehrungen2.regiondo.de/test",
            quantity: 2,
            numThreads: 1,
            status: .running,
            scanCount: 1542,
            ticketsAvailable: 0,
            lastScanAt: nil,
            eventId: "12345",
            ticketId: nil,
            createdAt: "2026-01-19T10:00:00Z",
            startedAt: "2026-01-19T10:00:05Z",
            completedAt: nil,
            errorMessage: nil,
            cartToken: nil
        ))
    }
}
