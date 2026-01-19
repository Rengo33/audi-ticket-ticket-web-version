import SwiftUI

struct CartsView: View {
    @ObservedObject var taskMonitor = TaskMonitor.shared
    @State private var timer = Timer.publish(every: 1, on: .main, in: .common).autoconnect()
    @State private var refreshTrigger = false
    
    var body: some View {
        NavigationStack {
            Group {
                if taskMonitor.carts.isEmpty {
                    ContentUnavailableView(
                        "No Active Carts",
                        systemImage: "cart",
                        description: Text("When a task finds tickets, they'll appear here")
                    )
                } else {
                    List {
                        ForEach(taskMonitor.carts) { cart in
                            CartRowView(cart: cart, refreshTrigger: refreshTrigger)
                        }
                    }
                    .refreshable {
                        await taskMonitor.fetchCarts()
                    }
                }
            }
            .navigationTitle("Carts")
            .onReceive(timer) { _ in
                refreshTrigger.toggle()
            }
        }
    }
}

struct CartRowView: View {
    let cart: Cart
    let refreshTrigger: Bool
    @ObservedObject var taskMonitor = TaskMonitor.shared
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text(cart.eventName)
                    .font(.headline)
                    .lineLimit(2)
                
                Spacer()
                
                if cart.isExpired {
                    Text("Expired")
                        .font(.caption)
                        .fontWeight(.medium)
                        .padding(.horizontal, 8)
                        .padding(.vertical, 4)
                        .background(Color.red)
                        .foregroundColor(.white)
                        .cornerRadius(8)
                } else if let remaining = cart.timeRemaining {
                    Text(remaining)
                        .font(.caption)
                        .fontWeight(.medium)
                        .monospacedDigit()
                        .padding(.horizontal, 8)
                        .padding(.vertical, 4)
                        .background(Color.orange)
                        .foregroundColor(.white)
                        .cornerRadius(8)
                }
            }
            
            HStack {
                VStack(alignment: .leading, spacing: 2) {
                    Text("Cart URL")
                        .font(.caption2)
                        .foregroundColor(.secondary)
                    Text(cart.cartUrl)
                        .font(.caption)
                        .foregroundColor(.secondary)
                        .lineLimit(1)
                }
                
                Spacer()
                
                Button(action: {
                    taskMonitor.openCheckout(for: cart)
                }) {
                    HStack {
                        Image(systemName: "safari")
                        Text("Checkout")
                    }
                    .fontWeight(.semibold)
                }
                .buttonStyle(.borderedProminent)
                .disabled(cart.isExpired)
            }
        }
        .padding(.vertical, 8)
        .opacity(cart.isExpired ? 0.5 : 1.0)
    }
}

#Preview {
    CartsView()
}
