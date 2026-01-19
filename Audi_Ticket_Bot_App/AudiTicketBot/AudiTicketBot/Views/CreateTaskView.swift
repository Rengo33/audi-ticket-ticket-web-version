import SwiftUI

struct CreateTaskView: View {
    @Environment(\.dismiss) private var dismiss
    @ObservedObject var taskMonitor = TaskMonitor.shared
    
    @State private var productUrl = ""
    @State private var quantity = 1
    @State private var numThreads = 1
    @State private var isCreating = false
    @State private var errorMessage: String?
    @State private var startImmediately = true
    
    private let validDomain = "audidefuehrungen2.regiondo.de"
    
    var isValidUrl: Bool {
        productUrl.contains(validDomain)
    }
    
    var body: some View {
        NavigationStack {
            Form {
                Section {
                    TextField("Event URL", text: $productUrl, prompt: Text("https://audidefuehrungen2.regiondo.de/..."))
                        .textContentType(.URL)
                        .keyboardType(.URL)
                        .autocapitalization(.none)
                        .autocorrectionDisabled()
                    
                    if !productUrl.isEmpty && !isValidUrl {
                        Text("URL must be from \(validDomain)")
                            .font(.caption)
                            .foregroundColor(.red)
                    }
                } header: {
                    Text("Target")
                } footer: {
                    Text("Paste the full URL of the event page.")
                }
                
                Section {
                    Stepper {
                        HStack {
                            Text("Quantity")
                            Spacer()
                            Text("\(quantity)")
                                .foregroundColor(.secondary)
                        }
                    } onIncrement: {
                        if quantity < 4 { quantity += 1 }
                    } onDecrement: {
                        if quantity > 1 { quantity -= 1 }
                    }
                    
                    Stepper {
                        HStack {
                            Text("Threads")
                            Spacer()
                            Text("\(numThreads)")
                                .foregroundColor(.secondary)
                        }
                    } onIncrement: {
                        if numThreads < 5 { numThreads += 1 }
                    } onDecrement: {
                        if numThreads > 1 { numThreads -= 1 }
                    }
                } header: {
                    Text("Configuration")
                }
                
                Section {
                    Toggle("Start Immediately", isOn: $startImmediately)
                }
                
                if let error = errorMessage {
                    Section {
                        Text(error)
                            .foregroundColor(.red)
                            .font(.subheadline)
                    }
                }
                
                Section {
                    Button(action: createTask) {
                        HStack {
                            Spacer()
                            if isCreating {
                                ProgressView()
                            } else {
                                Text("Create Task")
                                    .fontWeight(.semibold)
                            }
                            Spacer()
                        }
                    }
                    .disabled(!isValidUrl || isCreating)
                    .listRowBackground(isValidUrl ? Color.primary : Color.gray.opacity(0.1))
                    .foregroundColor(isValidUrl ? .white : .gray)
                }
            }
            .navigationTitle("New Task")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    Button("Cancel") {
                        dismiss()
                    }
                }
            }
        }
    }
    
    private func createTask() {
        guard isValidUrl else { return }
        
        isCreating = true
        errorMessage = nil
        
        Task {
            do {
                print("Creating task with URL: \(productUrl)")
                let task = try await taskMonitor.createTask(
                    productUrl: productUrl,
                    quantity: quantity,
                    numThreads: numThreads
                )
                print("Task created successfully: \(task.id)")
                
                if startImmediately {
                    print("Starting task immediately...")
                    await taskMonitor.startTask(task)
                }
                
                await MainActor.run {
                    dismiss()
                }
            } catch let error as APIService.APIError {
                await MainActor.run {
                    errorMessage = error.errorDescription
                    isCreating = false
                    print("API Error: \(error.errorDescription ?? "Unknown")")
                }
            } catch {
                await MainActor.run {
                    errorMessage = error.localizedDescription
                    isCreating = false
                    print("Error: \(error.localizedDescription)")
                }
            }
        }
    }
}

#Preview {
    CreateTaskView()
}
