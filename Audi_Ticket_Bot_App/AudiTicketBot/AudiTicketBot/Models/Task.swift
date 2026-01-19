import Foundation

struct TaskItem: Codable, Identifiable {
    let id: Int
    let productUrl: String
    let quantity: Int
    let numThreads: Int
    let status: TaskStatus
    let scanCount: Int
    let ticketsAvailable: Int
    let lastScanAt: String?
    let eventId: String?
    let ticketId: String?
    let createdAt: String
    let startedAt: String?
    let completedAt: String?
    let errorMessage: String?
    let cartToken: String?
    
    enum CodingKeys: String, CodingKey {
        case id
        case productUrl = "product_url"
        case quantity
        case numThreads = "num_threads"
        case status
        case scanCount = "scan_count"
        case ticketsAvailable = "tickets_available"
        case lastScanAt = "last_scan_at"
        case eventId = "event_id"
        case ticketId = "ticket_id"
        case createdAt = "created_at"
        case startedAt = "started_at"
        case completedAt = "completed_at"
        case errorMessage = "error_message"
        case cartToken = "cart_token"
    }
    
    /// Extract a display name from the product URL
    var displayName: String {
        guard let url = URL(string: productUrl) else { return "Task #\(id)" }
        let components = url.pathComponents.filter { $0 != "/" && !$0.isEmpty }
        if let lastComponent = components.last {
            return lastComponent
                .replacingOccurrences(of: "-", with: " ")
                .replacingOccurrences(of: "_", with: " ")
                .capitalized
        }
        return "Task #\(id)"
    }
}

struct TaskCreate: Codable {
    let productUrl: String
    let quantity: Int
    let numThreads: Int
    
    enum CodingKeys: String, CodingKey {
        case productUrl = "product_url"
        case quantity
        case numThreads = "num_threads"
    }
}

enum TaskStatus: String, Codable {
    case running = "running"
    case success = "success"
    case failed = "failed"
    case stopped = "stopped"
    case pending = "pending"
    
    var displayName: String {
        switch self {
        case .running: return "Running"
        case .success: return "Success"
        case .failed: return "Failed"
        case .stopped: return "Stopped"
        case .pending: return "Pending"
        }
    }
    
    var iconName: String {
        switch self {
        case .running: return "play.circle.fill"
        case .success: return "checkmark.circle.fill"
        case .failed: return "xmark.circle.fill"
        case .stopped: return "stop.circle.fill"
        case .pending: return "clock.fill"
        }
    }
}

struct TasksResponse: Codable {
    let tasks: [TaskItem]
    let total: Int
}
