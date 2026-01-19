import SwiftUI

struct LoginView: View {
    @ObservedObject var authManager = AuthManager.shared
    @State private var password = ""
    @FocusState private var isPasswordFocused: Bool
    
    var body: some View {
        NavigationStack {
            VStack(spacing: 30) {
                Spacer()
                
                // Logo / Title
                VStack(spacing: 12) {
                    Image(systemName: "ticket.fill")
                        .font(.system(size: 60))
                        .foregroundColor(.blue)
                    
                    Text("Audi Ticket Bot")
                        .font(.largeTitle)
                        .fontWeight(.bold)
                    
                    Text("Enter your password to continue")
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                }
                
                Spacer()
                
                // Login Form
                VStack(spacing: 16) {
                    SecureField("Password", text: $password)
                        .textFieldStyle(.roundedBorder)
                        .textContentType(.password)
                        .focused($isPasswordFocused)
                        .submitLabel(.go)
                        .onSubmit {
                            login()
                        }
                    
                    if let error = authManager.errorMessage {
                        Text(error)
                            .font(.caption)
                            .foregroundColor(.red)
                            .multilineTextAlignment(.center)
                    }
                    
                    Button(action: login) {
                        HStack {
                            if authManager.isLoading {
                                ProgressView()
                                    .progressViewStyle(CircularProgressViewStyle(tint: .white))
                                    .scaleEffect(0.8)
                            }
                            Text(authManager.isLoading ? "Logging in..." : "Login")
                        }
                        .frame(maxWidth: .infinity)
                        .padding()
                        .background(password.isEmpty ? Color.gray : Color.blue)
                        .foregroundColor(.white)
                        .cornerRadius(10)
                    }
                    .disabled(password.isEmpty || authManager.isLoading)
                }
                .padding(.horizontal, 30)
                
                Spacer()
                Spacer()
            }
            .navigationBarHidden(true)
        }
        .onAppear {
            isPasswordFocused = true
        }
    }
    
    private func login() {
        guard !password.isEmpty else { return }
        Task {
            await authManager.login(password: password)
        }
    }
}

#Preview {
    LoginView()
}
