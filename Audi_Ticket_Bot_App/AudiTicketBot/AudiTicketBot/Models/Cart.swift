import Foundation

struct Cart: Codable, Identifiable {
    let id: Int
    let token: String
    let taskId: Int?
    let productUrl: String
    let checkoutUrl: String?
    let quantity: Int
    let totalTime: Double?
    let createdAt: String
    let expiresAt: String
    let usedAt: String?
    
    enum CodingKeys: String, CodingKey {
        case id
        case token
        case taskId = "task_id"
        case productUrl = "product_url"
        case checkoutUrl = "checkout_url"
        case quantity
        case totalTime = "total_time"
        case createdAt = "created_at"
        case expiresAt = "expires_at"
        case usedAt = "used_at"
    }
    
    /// Parse the expiresAt date string into a Date object
    var expiryDate: Date? {
        Cart.parseDate(expiresAt)
    }
    
    var isExpired: Bool {
        guard let date = expiryDate else { return true }
        return date < Date()
    }
    
    var timeRemaining: String? {
        guard let expiryDate = expiryDate else { return nil }
        
        let remaining = expiryDate.timeIntervalSinceNow
        if remaining <= 0 { return "Expired" }
        
        let minutes = Int(remaining / 60)
        let seconds = Int(remaining) % 60
        return String(format: "%d:%02d", minutes, seconds)
    }
    
    /// Display name extracted from product URL
    var displayName: String {
        if let url = URL(string: productUrl),
           let lastComponent = url.pathComponents.last,
           !lastComponent.isEmpty {
            return lastComponent.replacingOccurrences(of: "-", with: " ").capitalized
        }
        return "Cart #\(id)"
    }
    
    /// Parse date from various formats the server might return
    static func parseDate(_ dateString: String) -> Date? {
        // Try ISO8601 with fractional seconds
        let iso8601Fractional = ISO8601DateFormatter()
        iso8601Fractional.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        if let date = iso8601Fractional.date(from: dateString) {
            return date
        }
        
        // Try ISO8601 without fractional seconds
        let iso8601 = ISO8601DateFormatter()
        iso8601.formatOptions = [.withInternetDateTime]
        if let date = iso8601.date(from: dateString) {
            return date
        }
        
        // Try common datetime format: "2026-01-19T10:30:00"
        let formatter1 = DateFormatter()
        formatter1.dateFormat = "yyyy-MM-dd'T'HH:mm:ss"
        formatter1.timeZone = TimeZone(identifier: "UTC")
        if let date = formatter1.date(from: dateString) {
            return date
        }
        
        // Try with microseconds: "2026-01-19T10:30:00.123456"
        let formatter2 = DateFormatter()
        formatter2.dateFormat = "yyyy-MM-dd'T'HH:mm:ss.SSSSSS"
        formatter2.timeZone = TimeZone(identifier: "UTC")
        if let date = formatter2.date(from: dateString) {
            return date
        }
        
        // Try Python default format: "2026-01-19 10:30:00.123456"
        let formatter3 = DateFormatter()
        formatter3.dateFormat = "yyyy-MM-dd HH:mm:ss.SSSSSS"
        formatter3.timeZone = TimeZone(identifier: "UTC")
        if let date = formatter3.date(from: dateString) {
            return date
        }
        
        // Try Python default without microseconds: "2026-01-19 10:30:00"
        let formatter4 = DateFormatter()
        formatter4.dateFormat = "yyyy-MM-dd HH:mm:ss"
        formatter4.timeZone = TimeZone(identifier: "UTC")
        if let date = formatter4.date(from: dateString) {
            return date
        }
        
        print("⚠️ Failed to parse date: \(dateString)")
        return nil
    }
}

struct CartsResponse: Codable {
    let carts: [Cart]
}
