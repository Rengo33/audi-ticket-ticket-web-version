import Foundation

struct TaskItem: Codable, Identifiable {
    let id: Int
    let eventName: String
    let eventUrl: String
    let status: TaskStatus
    let cartUrl: String?
    let createdAt: String
    let updatedAt: String
    
    enum CodingKeys: String, CodingKey {
        case id
        case eventName = "event_name"
        case eventUrl = "event_url"
        case status
        case cartUrl = "cart_url"
        case createdAt = "created_at"
        case updatedAt = "updated_at"
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
    
    var color: String {
        switch self {
        case .running: return "blue"
        case .success: return "green"
        case .failed: return "red"
        case .stopped: return "gray"
        case .pending: return "orange"
        }
    }
}

struct TasksResponse: Codable {
    let tasks: [TaskItem]
}
