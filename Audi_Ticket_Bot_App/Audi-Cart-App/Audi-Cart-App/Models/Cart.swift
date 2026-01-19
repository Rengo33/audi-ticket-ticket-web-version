import Foundation

struct Cart: Codable, Identifiable {
    let id: Int
    let taskId: Int
    let eventName: String
    let cartUrl: String
    let expiresAt: String?
    let createdAt: String
    
    enum CodingKeys: String, CodingKey {
        case id
        case taskId = "task_id"
        case eventName = "event_name"
        case cartUrl = "cart_url"
        case expiresAt = "expires_at"
        case createdAt = "created_at"
    }
    
    var isExpired: Bool {
        guard let expiresAt = expiresAt else { return false }
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        if let date = formatter.date(from: expiresAt) {
            return date < Date()
        }
        return false
    }
    
    var timeRemaining: String? {
        guard let expiresAt = expiresAt else { return nil }
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        guard let date = formatter.date(from: expiresAt) else { return nil }
        
        let remaining = date.timeIntervalSinceNow
        if remaining <= 0 { return "Expired" }
        
        let minutes = Int(remaining / 60)
        let seconds = Int(remaining) % 60
        return String(format: "%d:%02d", minutes, seconds)
    }
}

struct CartsResponse: Codable {
    let carts: [Cart]
}
