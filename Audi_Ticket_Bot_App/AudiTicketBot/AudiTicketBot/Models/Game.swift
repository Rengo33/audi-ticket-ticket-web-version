import Foundation

struct BayernGame: Codable, Identifiable {
    let id: String
    let title: String
    let opponent: String
    let location: String
    let url: String
    let imageUrl: String?
    let matchDate: String?
    let matchTime: String?
    let saleDate: String?
    let saleTime: String
    let isAvailable: Bool
    let status: String
    var isScheduled: Bool
    var scheduledTaskId: Int?
    
    enum CodingKeys: String, CodingKey {
        case id
        case title
        case opponent
        case location
        case url
        case imageUrl = "image_url"
        case matchDate = "match_date"
        case matchTime = "match_time"
        case saleDate = "sale_date"
        case saleTime = "sale_time"
        case isAvailable = "is_available"
        case status
        case isScheduled = "is_scheduled"
        case scheduledTaskId = "scheduled_task_id"
    }
    
    // Computed properties for display
    var formattedMatchDate: String {
        guard let matchDate = matchDate else { return "TBD" }
        let inputFormatter = ISO8601DateFormatter()
        inputFormatter.formatOptions = [.withFullDate]
        
        if let date = inputFormatter.date(from: matchDate) {
            let outputFormatter = DateFormatter()
            outputFormatter.dateStyle = .medium
            outputFormatter.locale = Locale(identifier: "de_DE")
            return outputFormatter.string(from: date)
        }
        return matchDate
    }
    
    var formattedSaleDate: String {
        guard let saleDate = saleDate else { return "Not announced" }
        let inputFormatter = ISO8601DateFormatter()
        inputFormatter.formatOptions = [.withFullDate]
        
        if let date = inputFormatter.date(from: saleDate) {
            let outputFormatter = DateFormatter()
            outputFormatter.dateStyle = .medium
            outputFormatter.locale = Locale(identifier: "de_DE")
            return outputFormatter.string(from: date)
        }
        return saleDate
    }
    
    var canSchedule: Bool {
        // Can schedule if sale date is in the future and not already scheduled
        guard let saleDate = saleDate, !isScheduled else { return false }
        
        let inputFormatter = ISO8601DateFormatter()
        inputFormatter.formatOptions = [.withFullDate]
        
        if let date = inputFormatter.date(from: saleDate) {
            return date > Date()
        }
        return false
    }
    
    var statusColor: String {
        switch status {
        case "on_sale": return "green"
        case "sold_out": return "red"
        case "upcoming": return "blue"
        default: return "gray"
        }
    }
    
    var statusDisplay: String {
        switch status {
        case "on_sale": return "On Sale"
        case "sold_out": return "Sold Out"
        case "upcoming": return "Upcoming"
        default: return status.capitalized
        }
    }
}

struct ScheduledTask: Codable, Identifiable {
    let id: Int
    let gameId: String
    let gameTitle: String
    let productUrl: String
    let quantity: Int
    let numThreads: Int
    let scheduledDate: String
    let status: String
    let taskId: Int?
    let createdAt: String
    
    enum CodingKeys: String, CodingKey {
        case id
        case gameId = "game_id"
        case gameTitle = "game_title"
        case productUrl = "product_url"
        case quantity
        case numThreads = "num_threads"
        case scheduledDate = "scheduled_date"
        case status
        case taskId = "task_id"
        case createdAt = "created_at"
    }
    
    var formattedScheduledDate: String {
        let inputFormatter = ISO8601DateFormatter()
        
        if let date = inputFormatter.date(from: scheduledDate) {
            let outputFormatter = DateFormatter()
            outputFormatter.dateStyle = .medium
            outputFormatter.timeStyle = .short
            outputFormatter.locale = Locale(identifier: "de_DE")
            return outputFormatter.string(from: date)
        }
        return scheduledDate
    }
}

struct ScheduleRequest: Codable {
    let gameId: String
    let quantity: Int
    let numThreads: Int
    
    enum CodingKeys: String, CodingKey {
        case gameId = "game_id"
        case quantity
        case numThreads = "num_threads"
    }
}
