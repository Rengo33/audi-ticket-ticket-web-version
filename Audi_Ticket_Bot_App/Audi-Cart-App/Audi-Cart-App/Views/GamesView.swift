import SwiftUI

struct GamesView: View {
    @StateObject private var viewModel = GamesViewModel()
    @ObservedObject var authManager = AuthManager.shared
    
    var body: some View {
        NavigationStack {
            Group {
                if viewModel.isLoading && viewModel.games.isEmpty {
                    ProgressView("Loading games...")
                } else if viewModel.games.isEmpty {
                    ContentUnavailableView(
                        "No Games",
                        systemImage: "sportscourt",
                        description: Text("No FC Bayern games found")
                    )
                } else {
                    List {
                        if !viewModel.scheduledTasks.isEmpty {
                            Section("Scheduled Tasks") {
                                ForEach(viewModel.scheduledTasks) { task in
                                    ScheduledTaskRow(task: task, viewModel: viewModel)
                                }
                            }
                        }
                        
                        Section("Upcoming Games") {
                            ForEach(viewModel.games) { game in
                                GameRow(game: game, viewModel: viewModel)
                            }
                        }
                    }
                    .refreshable {
                        await viewModel.refresh()
                    }
                }
            }
            .navigationTitle("FC Bayern Games")
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button(action: { authManager.logout() }) {
                        Image(systemName: "rectangle.portrait.and.arrow.right")
                    }
                }
            }
            .alert("Error", isPresented: .constant(viewModel.errorMessage != nil)) {
                Button("OK") { viewModel.errorMessage = nil }
            } message: {
                if let error = viewModel.errorMessage {
                    Text(error)
                }
            }
            .sheet(isPresented: $viewModel.showScheduleSheet) {
                if let game = viewModel.selectedGame {
                    ScheduleSheet(game: game, viewModel: viewModel)
                }
            }
        }
        .task {
            await viewModel.refresh()
        }
    }
}

struct GameRow: View {
    let game: BayernGame
    @ObservedObject var viewModel: GamesViewModel
    
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                VStack(alignment: .leading) {
                    Text(game.opponent)
                        .font(.headline)
                    
                    HStack {
                        Image(systemName: "mappin.circle.fill")
                            .foregroundColor(.secondary)
                            .font(.caption)
                        Text(game.location)
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                }
                
                Spacer()
                
                GameStatusBadge(status: game.status)
            }
            
            HStack {
                VStack(alignment: .leading) {
                    HStack {
                        Image(systemName: "calendar")
                            .foregroundColor(.blue)
                            .font(.caption)
                        Text("Match: \(game.formattedMatchDate)")
                            .font(.caption)
                    }
                    
                    HStack {
                        Image(systemName: "tag.fill")
                            .foregroundColor(.orange)
                            .font(.caption)
                        Text("Sale: \(game.formattedSaleDate)")
                            .font(.caption)
                    }
                }
                
                Spacer()
                
                if game.isScheduled {
                    Label("Scheduled", systemImage: "clock.fill")
                        .font(.caption)
                        .foregroundColor(.green)
                } else if game.canSchedule {
                    Button("Schedule") {
                        viewModel.selectedGame = game
                        viewModel.showScheduleSheet = true
                    }
                    .buttonStyle(.borderedProminent)
                    .controlSize(.small)
                }
            }
        }
        .padding(.vertical, 4)
    }
}

struct GameStatusBadge: View {
    let status: String
    
    var body: some View {
        Text(statusText)
            .font(.caption)
            .fontWeight(.semibold)
            .padding(.horizontal, 8)
            .padding(.vertical, 4)
            .background(statusColor.opacity(0.2))
            .foregroundColor(statusColor)
            .cornerRadius(6)
    }
    
    var statusText: String {
        switch status {
        case "on_sale": return "On Sale"
        case "sold_out": return "Sold Out"
        case "upcoming": return "Upcoming"
        default: return status.capitalized
        }
    }
    
    var statusColor: Color {
        switch status {
        case "on_sale": return .green
        case "sold_out": return .red
        case "upcoming": return .blue
        default: return .gray
        }
    }
}

struct ScheduledTaskRow: View {
    let task: ScheduledTask
    @ObservedObject var viewModel: GamesViewModel
    
    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(task.gameTitle)
                .font(.headline)
            
            HStack {
                Label("\(task.quantity) tickets", systemImage: "ticket.fill")
                    .font(.caption)
                
                Spacer()
                
                Label(task.formattedScheduledDate, systemImage: "clock.fill")
                    .font(.caption)
                    .foregroundColor(.green)
            }
            
            HStack {
                ScheduleStatusBadge(status: task.status)
                
                Spacer()
                
                if task.status == "scheduled" {
                    Button("Cancel") {
                        Task {
                            await viewModel.cancelScheduledTask(task)
                        }
                    }
                    .buttonStyle(.bordered)
                    .controlSize(.small)
                    .tint(.red)
                }
            }
        }
        .padding(.vertical, 4)
    }
}

struct ScheduleStatusBadge: View {
    let status: String
    
    var body: some View {
        HStack {
            Circle()
                .fill(statusColor)
                .frame(width: 8, height: 8)
            Text(status.capitalized)
                .font(.caption)
        }
    }
    
    var statusColor: Color {
        switch status {
        case "scheduled": return .blue
        case "triggered": return .green
        case "failed": return .red
        case "cancelled": return .gray
        default: return .gray
        }
    }
}

struct ScheduleSheet: View {
    let game: BayernGame
    @ObservedObject var viewModel: GamesViewModel
    @Environment(\.dismiss) var dismiss
    
    @State private var quantity: Int = 4
    @State private var threads: Int = 5
    @State private var isScheduling = false
    
    var body: some View {
        NavigationStack {
            Form {
                Section("Game") {
                    VStack(alignment: .leading, spacing: 6) {
                        Text(game.title)
                            .font(.headline)
                        
                        HStack {
                            Label(game.location, systemImage: "mappin.circle.fill")
                            Spacer()
                            Label(game.formattedMatchDate, systemImage: "calendar")
                        }
                        .font(.caption)
                        .foregroundColor(.secondary)
                    }
                }
                
                Section("Schedule Info") {
                    HStack {
                        Text("Sale Date")
                        Spacer()
                        Text(game.formattedSaleDate)
                            .foregroundColor(.secondary)
                    }
                    
                    HStack {
                        Text("Start Time")
                        Spacer()
                        Text("7:00 AM (German time)")
                            .foregroundColor(.secondary)
                    }
                }
                
                Section("Configuration") {
                    Stepper("Quantity: \(quantity)", value: $quantity, in: 1...10)
                    Stepper("Threads: \(threads)", value: $threads, in: 1...20)
                }
                
                Section {
                    Button(action: scheduleTask) {
                        HStack {
                            Spacer()
                            if isScheduling {
                                ProgressView()
                            } else {
                                Label("Schedule Task", systemImage: "clock.badge.checkmark")
                            }
                            Spacer()
                        }
                    }
                    .disabled(isScheduling)
                }
            }
            .navigationTitle("Schedule Task")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    Button("Cancel") {
                        dismiss()
                    }
                }
            }
        }
    }
    
    func scheduleTask() {
        isScheduling = true
        
        Task {
            await viewModel.scheduleGame(game, quantity: quantity, threads: threads)
            isScheduling = false
            dismiss()
        }
    }
}

// MARK: - View Model

@MainActor
final class GamesViewModel: ObservableObject {
    @Published var games: [BayernGame] = []
    @Published var scheduledTasks: [ScheduledTask] = []
    @Published var isLoading = false
    @Published var errorMessage: String?
    @Published var showScheduleSheet = false
    @Published var selectedGame: BayernGame?
    
    func refresh() async {
        guard let token = AuthManager.shared.token else {
            errorMessage = "Not authenticated"
            return
        }
        
        isLoading = true
        
        do {
            async let gamesTask = APIService.shared.getGames(token: token)
            async let scheduledTask = APIService.shared.getScheduledTasks(token: token)
            
            let (fetchedGames, fetchedScheduled) = try await (gamesTask, scheduledTask)
            
            games = fetchedGames
            scheduledTasks = fetchedScheduled
            errorMessage = nil
            
        } catch let error as APIService.APIError {
            if case .unauthorized = error {
                AuthManager.shared.handleUnauthorized()
            } else {
                errorMessage = error.errorDescription
            }
        } catch {
            errorMessage = "Failed to load games: \(error.localizedDescription)"
        }
        
        isLoading = false
    }
    
    func scheduleGame(_ game: BayernGame, quantity: Int, threads: Int) async {
        guard let token = AuthManager.shared.token else {
            errorMessage = "Not authenticated"
            return
        }
        
        do {
            try await APIService.shared.scheduleGame(
                gameId: game.id,
                quantity: quantity,
                numThreads: threads,
                token: token
            )
            
            // Refresh data
            await refresh()
            
        } catch let error as APIService.APIError {
            if case .unauthorized = error {
                AuthManager.shared.handleUnauthorized()
            } else {
                errorMessage = error.errorDescription
            }
        } catch {
            errorMessage = "Failed to schedule: \(error.localizedDescription)"
        }
    }
    
    func cancelScheduledTask(_ task: ScheduledTask) async {
        guard let token = AuthManager.shared.token else {
            errorMessage = "Not authenticated"
            return
        }
        
        do {
            try await APIService.shared.cancelScheduledTask(id: task.id, token: token)
            
            // Refresh data
            await refresh()
            
        } catch let error as APIService.APIError {
            if case .unauthorized = error {
                AuthManager.shared.handleUnauthorized()
            } else {
                errorMessage = error.errorDescription
            }
        } catch {
            errorMessage = "Failed to cancel: \(error.localizedDescription)"
        }
    }
}

#Preview {
    GamesView()
}
