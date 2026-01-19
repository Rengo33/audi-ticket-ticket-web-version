import SwiftUI
import Combine

struct CartsView: View {
    @ObservedObject var taskMonitor = TaskMonitor.shared
    @State private var timer = Timer.publish(every: 1, on: .main, in: .common).autoconnect()
    @State private var currentTime = Date()
    @State private var showCheckout = false
    @State private var checkoutURL: URL?
    
    /// Only show carts that haven't expired
    var validCarts: [Cart] {
        // Use currentTime to force re-evaluation on timer tick
        let _ = currentTime
        return taskMonitor.carts.filter { !$0.isExpired }
    }
    
    var body: some View {
        NavigationStack {
            ZStack {
                Color(uiColor: .systemGroupedBackground)
                    .ignoresSafeArea()
                
                if validCarts.isEmpty {
                    ContentUnavailableView {
                        Label("No Active Carts", systemImage: "cart")
                    } description: {
                        Text("When a task finds tickets, they'll appear here.")
                    }
                } else {
                    ScrollView {
                        LazyVStack(spacing: 16) {
                            ForEach(validCarts) { cart in
                                CartRowView(cart: cart, currentTime: currentTime, onCheckout: { url in
                                    checkoutURL = url
                                    showCheckout = true
                                })
                            }
                        }
                        .padding()
                    }
                    .refreshable {
                        await taskMonitor.fetchCarts()
                    }
                }
            }
            .navigationTitle("Carts (\(validCarts.count))")
            .onReceive(timer) { _ in
                currentTime = Date()
            }
            .safariSheet(isPresented: $showCheckout, url: checkoutURL)
        }
    }
}

struct CartRowView: View {
    let cart: Cart
    let currentTime: Date
    var onCheckout: (URL) -> Void
    @ObservedObject var taskMonitor = TaskMonitor.shared
    
    /// Calculate time remaining based on current time
    var timeRemaining: TimeInterval {
        guard let expiryDate = cart.expiryDate else { return 0 }
        return max(0, expiryDate.timeIntervalSince(currentTime))
    }
    
    var timeString: String {
        let remaining = timeRemaining
        let minutes = Int(remaining / 60)
        let seconds = Int(remaining) % 60
        return String(format: "%d:%02d", minutes, seconds)
    }
    
    var progress: Double {
        // Assuming 10 minutes total hold time? Or just show remaining relative to something?
        // Let's just create a nice visual. If we assume 15 mins (900s) default
        return min(1.0, timeRemaining / 900.0)
    }
    
    var timeColor: Color {
        if timeRemaining <= 60 { return .red }
        if timeRemaining <= 180 { return .orange }
        return .blue
    }
    
    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            // Header
            HStack(alignment: .center) {
                // Blue Icon Circle
                ZStack {
                    Circle()
                        .fill(Color.blue.opacity(0.1))
                        .frame(width: 44, height: 44)
                    
                    Image(systemName: "cart.fill")
                        .font(.system(size: 20))
                        .foregroundColor(.blue)
                }
                .padding(.trailing, 4)
                
                VStack(alignment: .leading, spacing: 4) {
                    Text(cart.displayName)
                        .font(.system(size: 16, weight: .bold))
                        .foregroundColor(.primary)
                        .lineLimit(2)
                    
                    Text(cart.productUrl)
                        .font(.system(size: 12))
                        .foregroundColor(.secondary)
                        .lineLimit(1)
                }
                
                Spacer()
                
                // Timer
                HStack(spacing: 4) {
                    Image(systemName: "timer")
                        .font(.system(size: 12))
                    Text(timeString)
                        .font(.system(size: 14, weight: .bold, design: .monospaced))
                }
                .foregroundColor(timeColor)
                .padding(.horizontal, 10)
                .padding(.vertical, 6)
                .background(Color.blue.opacity(0.1))
                .cornerRadius(8)
            }
            .padding(16)
            
            // Progress Bar
            GeometryReader { geometry in
                ZStack(alignment: .leading) {
                    Rectangle()
                        .fill(Color.gray.opacity(0.1))
                    
                    Rectangle()
                        .fill(timeColor)
                        .frame(width: geometry.size.width * CGFloat(progress))
                        .animation(.linear(duration: 1), value: progress)
                }
            }
            .frame(height: 4)
            
            Button(action: {
                if let url = taskMonitor.getCheckoutURL(for: cart) {
                    onCheckout(url)
                }
            }) {
                HStack {
                    Spacer()
                    Text("Proceed to Checkout")
                        .font(.system(size: 16, weight: .semibold))
                    Image(systemName: "arrow.right")
                        .font(.system(size: 14, weight: .bold))
                    Spacer()
                }
                .foregroundColor(.white)
                .padding(.vertical, 16)
                .background(Color.blue)
            }
        }
        .background(Color.white)
        .cornerRadius(16)
        .shadow(color: Color.black.opacity(0.05), radius: 10, x: 0, y: 5)
        .clipShape(RoundedRectangle(cornerRadius: 16))
    }
}

#Preview {
    CartsView()
}
