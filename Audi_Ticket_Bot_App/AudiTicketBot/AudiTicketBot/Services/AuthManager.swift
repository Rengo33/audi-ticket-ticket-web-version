import Foundation
import SwiftUI
import Combine

@MainActor
final class AuthManager: ObservableObject {
    static let shared = AuthManager()
    
    @Published var isAuthenticated = false
    @Published var isLoading = false
    @Published var errorMessage: String?
    
    private let tokenKey = "auth_token"
    
    var token: String? {
        try? KeychainHelper.shared.readString(forKey: tokenKey)
    }
    
    private init() {
        // Check if user is already authenticated
        checkExistingAuth()
    }
    
    // MARK: - Authentication Check
    func checkExistingAuth() {
        isAuthenticated = KeychainHelper.shared.exists(forKey: tokenKey)
    }
    
    // MARK: - Login
    func login(password: String) async {
        isLoading = true
        errorMessage = nil
        
        do {
            let token = try await APIService.shared.login(password: password)
            try KeychainHelper.shared.save(token, forKey: tokenKey)
            isAuthenticated = true
        } catch let error as APIService.APIError {
            errorMessage = error.errorDescription
        } catch {
            errorMessage = "Login failed: \(error.localizedDescription)"
        }
        
        isLoading = false
    }
    
    // MARK: - Logout
    func logout() {
        KeychainHelper.shared.delete(forKey: tokenKey)
        isAuthenticated = false
        errorMessage = nil
    }
    
    // MARK: - Handle Unauthorized
    func handleUnauthorized() {
        logout()
        errorMessage = "Session expired. Please log in again."
    }
}
