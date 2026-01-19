import SwiftUI
import UserNotifications

@main
struct AudiTicketBotApp: App {
    @UIApplicationDelegateAdaptor(AppDelegate.self) var appDelegate
    
    var body: some Scene {
        WindowGroup {
            ContentView()
        }
    }
}

class AppDelegate: NSObject, UIApplicationDelegate, UNUserNotificationCenterDelegate {
    func application(_ application: UIApplication, didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey : Any]? = nil) -> Bool {
        // Set notification delegate
        UNUserNotificationCenter.current().delegate = self
        
        // Register notification categories
        registerNotificationCategories()
        
        // Clear badge on launch
        application.applicationIconBadgeNumber = 0
        
        return true
    }
    
    func applicationDidBecomeActive(_ application: UIApplication) {
        // Clear badge when app becomes active
        application.applicationIconBadgeNumber = 0
    }
    
    // MARK: - Notification Categories
    private func registerNotificationCategories() {
        let checkoutAction = UNNotificationAction(
            identifier: "CHECKOUT_ACTION",
            title: "Open Checkout",
            options: [.foreground]
        )
        
        let cartSuccessCategory = UNNotificationCategory(
            identifier: "CART_SUCCESS",
            actions: [checkoutAction],
            intentIdentifiers: [],
            options: []
        )
        
        UNUserNotificationCenter.current().setNotificationCategories([cartSuccessCategory])
    }
    
    // MARK: - UNUserNotificationCenterDelegate
    
    // Handle notification when app is in foreground
    func userNotificationCenter(_ center: UNUserNotificationCenter, willPresent notification: UNNotification, withCompletionHandler completionHandler: @escaping (UNNotificationPresentationOptions) -> Void) {
        // Show notification even when app is in foreground
        completionHandler([.banner, .sound, .badge])
    }
    
    // Handle notification tap
    func userNotificationCenter(_ center: UNUserNotificationCenter, didReceive response: UNNotificationResponse, withCompletionHandler completionHandler: @escaping () -> Void) {
        let identifier = response.notification.request.identifier
        
        // Handle checkout action
        if response.actionIdentifier == "CHECKOUT_ACTION" || response.actionIdentifier == UNNotificationDefaultActionIdentifier {
            // Navigate to carts tab - this will be handled by the app state
            DispatchQueue.main.async {
                // Post notification to switch to carts tab
                NotificationCenter.default.post(name: .openCartsTab, object: nil)
            }
        }
        
        completionHandler()
    }
}

// MARK: - Notification Names
extension Notification.Name {
    static let openCartsTab = Notification.Name("openCartsTab")
}
