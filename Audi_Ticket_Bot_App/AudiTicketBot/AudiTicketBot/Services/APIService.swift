import Foundation

final class APIService {
    static let shared = APIService()
    private init() {}
    
    // MARK: - Configuration
    var baseURL: String {
        // Update this with your actual server URL
        return "http://13.53.151.166/api"
    }
    
    enum APIError: Error, LocalizedError {
        case invalidURL
        case noData
        case decodingError
        case unauthorized
        case serverError(Int)
        case networkError(Error)
        
        var errorDescription: String? {
            switch self {
            case .invalidURL:
                return "Invalid URL"
            case .noData:
                return "No data received"
            case .decodingError:
                return "Failed to decode response"
            case .unauthorized:
                return "Unauthorized - please log in again"
            case .serverError(let code):
                return "Server error: \(code)"
            case .networkError(let error):
                return "Network error: \(error.localizedDescription)"
            }
        }
    }
    
    // MARK: - Authentication
    func login(password: String) async throws -> String {
        let url = URL(string: "\(baseURL)/auth/login")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        let body = ["password": password]
        request.httpBody = try JSONEncoder().encode(body)
        
        let (data, response) = try await URLSession.shared.data(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.noData
        }
        
        if httpResponse.statusCode == 401 {
            throw APIError.unauthorized
        }
        
        guard httpResponse.statusCode == 200 else {
            throw APIError.serverError(httpResponse.statusCode)
        }
        
        struct LoginResponse: Codable {
            let token: String
        }
        
        let loginResponse = try JSONDecoder().decode(LoginResponse.self, from: data)
        return loginResponse.token
    }
    
    // MARK: - Tasks
    func getTasks(token: String) async throws -> [TaskItem] {
        let url = URL(string: "\(baseURL)/tasks")!
        var request = URLRequest(url: url)
        request.setValue(token, forHTTPHeaderField: "X-Auth-Token")
        
        let (data, response) = try await URLSession.shared.data(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.noData
        }
        
        if httpResponse.statusCode == 401 {
            throw APIError.unauthorized
        }
        
        guard httpResponse.statusCode == 200 else {
            throw APIError.serverError(httpResponse.statusCode)
        }
        
        let tasksResponse = try JSONDecoder().decode(TasksResponse.self, from: data)
        return tasksResponse.tasks
    }
    
    // MARK: - Carts
    func getCarts(token: String) async throws -> [Cart] {
        let url = URL(string: "\(baseURL)/carts")!
        var request = URLRequest(url: url)
        request.setValue(token, forHTTPHeaderField: "X-Auth-Token")
        
        let (data, response) = try await URLSession.shared.data(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.noData
        }
        
        if httpResponse.statusCode == 401 {
            throw APIError.unauthorized
        }
        
        guard httpResponse.statusCode == 200 else {
            throw APIError.serverError(httpResponse.statusCode)
        }
        
        // API returns array directly, not wrapped in {"carts": [...]}
        let carts = try JSONDecoder().decode([Cart].self, from: data)
        return carts
    }
    
    // MARK: - Task Actions
    func startTask(id: Int, token: String) async throws {
        let url = URL(string: "\(baseURL)/tasks/\(id)/start")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue(token, forHTTPHeaderField: "X-Auth-Token")
        
        let (data, response) = try await URLSession.shared.data(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.noData
        }
        
        print("Start task response status: \(httpResponse.statusCode)")
        if let responseStr = String(data: data, encoding: .utf8) {
            print("Start task response: \(responseStr)")
        }
        
        if httpResponse.statusCode == 401 {
            throw APIError.unauthorized
        }
        
        // Accept 200, 201, or 202 for async operations
        guard httpResponse.statusCode >= 200 && httpResponse.statusCode < 300 else {
            throw APIError.serverError(httpResponse.statusCode)
        }
    }
    
    func stopTask(id: Int, token: String) async throws {
        let url = URL(string: "\(baseURL)/tasks/\(id)/stop")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue(token, forHTTPHeaderField: "X-Auth-Token")
        
        let (data, response) = try await URLSession.shared.data(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.noData
        }
        
        print("Stop task response status: \(httpResponse.statusCode)")
        if let responseStr = String(data: data, encoding: .utf8) {
            print("Stop task response: \(responseStr)")
        }
        
        if httpResponse.statusCode == 401 {
            throw APIError.unauthorized
        }
        
        // Accept any 2xx status code
        guard httpResponse.statusCode >= 200 && httpResponse.statusCode < 300 else {
            throw APIError.serverError(httpResponse.statusCode)
        }
    }
    
    // MARK: - Create Task
    func createTask(productUrl: String, quantity: Int, numThreads: Int, token: String) async throws -> TaskItem {
        let url = URL(string: "\(baseURL)/tasks")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue(token, forHTTPHeaderField: "X-Auth-Token")
        
        let body = TaskCreate(productUrl: productUrl, quantity: quantity, numThreads: numThreads)
        request.httpBody = try JSONEncoder().encode(body)
        
        let (data, response) = try await URLSession.shared.data(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.noData
        }
        
        print("Create task response status: \(httpResponse.statusCode)")
        if let responseStr = String(data: data, encoding: .utf8) {
            print("Create task response: \(responseStr)")
        }
        
        if httpResponse.statusCode == 401 {
            throw APIError.unauthorized
        }
        
        if httpResponse.statusCode == 400 {
            if let responseStr = String(data: data, encoding: .utf8) {
                print("Create task 400 error: \(responseStr)")
            }
            throw APIError.serverError(400)
        }
        
        // Accept both 200 and 201 status codes
        guard httpResponse.statusCode == 200 || httpResponse.statusCode == 201 else {
            throw APIError.serverError(httpResponse.statusCode)
        }
        
        do {
            let task = try JSONDecoder().decode(TaskItem.self, from: data)
            return task
        } catch {
            print("Decoding error: \(error)")
            throw APIError.decodingError
        }
    }
    
    // MARK: - Delete Task
    func deleteTask(id: Int, token: String) async throws {
        let url = URL(string: "\(baseURL)/tasks/\(id)")!
        var request = URLRequest(url: url)
        request.httpMethod = "DELETE"
        request.setValue(token, forHTTPHeaderField: "X-Auth-Token")
        
        let (data, response) = try await URLSession.shared.data(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.noData
        }
        
        print("Delete task response status: \(httpResponse.statusCode)")
        if let responseStr = String(data: data, encoding: .utf8) {
            print("Delete task response: \(responseStr)")
        }
        
        if httpResponse.statusCode == 401 {
            throw APIError.unauthorized
        }
        
        // Accept 200, 204 (No Content), or any 2xx
        guard httpResponse.statusCode >= 200 && httpResponse.statusCode < 300 else {
            throw APIError.serverError(httpResponse.statusCode)
        }
    }
    
    // MARK: - Games
    func getGames(token: String) async throws -> [BayernGame] {
        let url = URL(string: "\(baseURL)/games")!
        var request = URLRequest(url: url)
        request.setValue(token, forHTTPHeaderField: "X-Auth-Token")
        
        let (data, response) = try await URLSession.shared.data(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.noData
        }
        
        if httpResponse.statusCode == 401 {
            throw APIError.unauthorized
        }
        
        guard httpResponse.statusCode == 200 else {
            throw APIError.serverError(httpResponse.statusCode)
        }
        
        return try JSONDecoder().decode([BayernGame].self, from: data)
    }
    
    func scheduleGame(gameId: String, quantity: Int, numThreads: Int, token: String) async throws {
        let url = URL(string: "\(baseURL)/games/schedule")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue(token, forHTTPHeaderField: "X-Auth-Token")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        let body = ScheduleRequest(gameId: gameId, quantity: quantity, numThreads: numThreads)
        request.httpBody = try JSONEncoder().encode(body)
        
        let (_, response) = try await URLSession.shared.data(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.noData
        }
        
        if httpResponse.statusCode == 401 {
            throw APIError.unauthorized
        }
        
        guard httpResponse.statusCode == 200 else {
            throw APIError.serverError(httpResponse.statusCode)
        }
    }
    
    func getScheduledTasks(token: String) async throws -> [ScheduledTask] {
        let url = URL(string: "\(baseURL)/games/scheduled")!
        var request = URLRequest(url: url)
        request.setValue(token, forHTTPHeaderField: "X-Auth-Token")
        
        let (data, response) = try await URLSession.shared.data(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.noData
        }
        
        if httpResponse.statusCode == 401 {
            throw APIError.unauthorized
        }
        
        guard httpResponse.statusCode == 200 else {
            throw APIError.serverError(httpResponse.statusCode)
        }
        
        return try JSONDecoder().decode([ScheduledTask].self, from: data)
    }
    
    func cancelScheduledTask(id: Int, token: String) async throws {
        let url = URL(string: "\(baseURL)/games/scheduled/\(id)")!
        var request = URLRequest(url: url)
        request.httpMethod = "DELETE"
        request.setValue(token, forHTTPHeaderField: "X-Auth-Token")
        
        let (_, response) = try await URLSession.shared.data(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.noData
        }
        
        if httpResponse.statusCode == 401 {
            throw APIError.unauthorized
        }
        
        guard httpResponse.statusCode == 200 else {
            throw APIError.serverError(httpResponse.statusCode)
        }
    }
}
