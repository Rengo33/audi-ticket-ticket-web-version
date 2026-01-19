import Foundation
import UserNotifications
import SwiftUI

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
    func startTask(_ task: TaskItem) async {
        guard let token = AuthManager.shared.token else { return }
        
        do {
            try await APIService.shared.startTask(id: task.id, token: token)
            await fetchTasks()
        } catch {
            errorMessage = "Failed to start task"
        }
    }
    
    func stopTask(_ task: TaskItem) async {
        guard let token = AuthManager.shared.token else { return }
        
        do {
            try await APIService.shared.stopTask(id: task.id, token: token)
            await fetchTasks()
        } catch {
            errorMessage = "Failed to stop task"
        }
    }
    
    // MARK: - Notifications
    private func sendSuccessNotification(for task: TaskItem) async {
        let content = UNMutableNotificationContent()
        content.title = "🎉 Cart Success!"
        content.body = "Ticket for '\(task.eventName)' added to cart! Open the app to checkout."
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
    func openCheckout(for cart: Cart) {
        guard let url = URL(string: cart.cartUrl) else { return }
        UIApplication.shared.open(url)
    }
}
