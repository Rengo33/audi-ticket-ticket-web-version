import Foundation
import UserNotifications
import SwiftUI
import Combine

@MainActor
final class TaskMonitor: ObservableObject {
    static let shared = TaskMonitor()
    
    @Published var tasks: [TaskItem] = []
    @Published var carts: [Cart] = []
    @Published var isLoading = false
    @Published var errorMessage: String?
    
    private var pollingTimer: Timer?
    private var previousTaskStatuses: [Int: TaskStatus] = [:]
    private let pollingInterval: TimeInterval = 5.0
    
    private init() {
        requestNotificationPermission()
    }
    
    // MARK: - Notification Permission
    func requestNotificationPermission() {
        UNUserNotificationCenter.current().requestAuthorization(options: [.alert, .badge, .sound]) { granted, error in
            if let error = error {
                print("Notification permission error: \(error)")
            }
            print("Notification permission granted: \(granted)")
        }
    }
    
    // MARK: - Polling Control
    func startPolling() {
        stopPolling()
        
        // Initial fetch
        Task {
            await fetchTasks()
            await fetchCarts()
        }
        
        // Start timer
        pollingTimer = Timer.scheduledTimer(withTimeInterval: pollingInterval, repeats: true) { [weak self] _ in
            Task { @MainActor in
                await self?.fetchTasks()
                await self?.fetchCarts()
            }
        }
    }
    
    func stopPolling() {
        pollingTimer?.invalidate()
        pollingTimer = nil
    }
    
    // MARK: - Fetch Tasks
    func fetchTasks() async {
        guard let token = AuthManager.shared.token else {
            errorMessage = "Not authenticated"
            return
        }
        
        do {
            let newTasks = try await APIService.shared.getTasks(token: token)
            
            // Check for status changes to "success"
            for task in newTasks {
                if let previousStatus = previousTaskStatuses[task.id],
                   previousStatus != .success,
                   task.status == .success {
                    // Task just became successful!
                    await sendSuccessNotification(for: task)
                }
            }
            
            // Update previous statuses
            previousTaskStatuses = Dictionary(uniqueKeysWithValues: newTasks.map { ($0.id, $0.status) })
            
            tasks = newTasks
            errorMessage = nil
            
        } catch let error as APIService.APIError {
            if case .unauthorized = error {
                AuthManager.shared.handleUnauthorized()
            } else {
                errorMessage = error.errorDescription
            }
        } catch {
            errorMessage = "Failed to fetch tasks: \(error.localizedDescription)"
        }
    }
    
    // MARK: - Fetch Carts
    func fetchCarts() async {
        guard let token = AuthManager.shared.token else { return }
        
        do {
            carts = try await APIService.shared.getCarts(token: token)
        } catch let error as APIService.APIError {
            if case .unauthorized = error {
                AuthManager.shared.handleUnauthorized()
            }
        } catch {
            print("Failed to fetch carts: \(error)")
        }
    }
    
    // MARK: - Task Actions
    func createTask(productUrl: String, quantity: Int, numThreads: Int) async throws -> TaskItem {
        guard let token = AuthManager.shared.token else {
            throw APIService.APIError.unauthorized
        }
        
        let task = try await APIService.shared.createTask(
            productUrl: productUrl,
            quantity: quantity,
            numThreads: numThreads,
            token: token
        )
        
        await fetchTasks()
        return task
    }
    
    func startTask(_ task: TaskItem) async {
        guard let token = AuthManager.shared.token else { 
            errorMessage = "Not authenticated"
            return 
        }
        
        do {
            try await APIService.shared.startTask(id: task.id, token: token)
            await fetchTasks()
        } catch let error as APIService.APIError {
            errorMessage = "Failed to start task: \(error.errorDescription ?? "Unknown error")"
            print("Start task error: \(error)")
        } catch {
            errorMessage = "Failed to start task: \(error.localizedDescription)"
            print("Start task error: \(error)")
        }
    }
    
    func stopTask(_ task: TaskItem) async {
        guard let token = AuthManager.shared.token else { 
            errorMessage = "Not authenticated"
            return 
        }
        
        do {
            try await APIService.shared.stopTask(id: task.id, token: token)
            await fetchTasks()
        } catch let error as APIService.APIError {
            errorMessage = "Failed to stop task: \(error.errorDescription ?? "Unknown error")"
            print("Stop task error: \(error)")
        } catch {
            errorMessage = "Failed to stop task: \(error.localizedDescription)"
            print("Stop task error: \(error)")
        }
    }
    
    func deleteTask(_ task: TaskItem) async {
        guard let token = AuthManager.shared.token else { 
            errorMessage = "Not authenticated"
            return 
        }
        
        do {
            try await APIService.shared.deleteTask(id: task.id, token: token)
            await fetchTasks()
        } catch let error as APIService.APIError {
            errorMessage = "Failed to delete task: \(error.errorDescription ?? "Unknown error")"
            print("Delete task error: \(error)")
        } catch {
            errorMessage = "Failed to delete task: \(error.localizedDescription)"
            print("Delete task error: \(error)")
        }
    }
    
    func deleteAllTasks() async {
        guard let token = AuthManager.shared.token else { 
            errorMessage = "Not authenticated"
            return 
        }
        
        // Create a copy of tasks to iterate
        let tasksToDelete = tasks
        
        for task in tasksToDelete {
            do {
                try await APIService.shared.deleteTask(id: task.id, token: token)
            } catch {
                print("Failed to delete task \(task.id): \(error)")
                // Continue trying to delete others even if one fails
            }
        }
        
        // Refresh list once at the end
        await fetchTasks()
    }
    
    // MARK: - Notifications
    private func sendSuccessNotification(for task: TaskItem) async {
        let content = UNMutableNotificationContent()
        content.title = "🎉 Cart Success!"
        content.body = "Ticket for '\(task.displayName)' added to cart! Open the app to checkout."
        content.sound = .default
        content.badge = 1
        
        // Add category for quick actions
        content.categoryIdentifier = "CART_SUCCESS"
        
        let request = UNNotificationRequest(
            identifier: "cart-success-\(task.id)",
            content: content,
            trigger: nil // Deliver immediately
        )
        
        do {
            try await UNUserNotificationCenter.current().add(request)
        } catch {
            print("Failed to send notification: \(error)")
        }
    }
    
    // MARK: - Cart Actions
    func getCheckoutURL(for cart: Cart) -> URL? {
        // Construct checkout URL: server/checkout/{token}/cart
        let baseServer = APIService.shared.baseURL.replacingOccurrences(of: "/api", with: "")
        let urlString = "\(baseServer)/checkout/\(cart.token)/cart"
        return URL(string: urlString)
    }
    
    func openCheckout(for cart: Cart) {
        guard let url = getCheckoutURL(for: cart) else { return }
        UIApplication.shared.open(url)
    }
}
