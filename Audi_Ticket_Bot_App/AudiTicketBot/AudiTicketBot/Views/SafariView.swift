import SwiftUI
import SafariServices

struct SafariView: UIViewControllerRepresentable {
    let url: URL
    
    func makeUIViewController(context: Context) -> SFSafariViewController {
        let config = SFSafariViewController.Configuration()
        config.entersReaderIfAvailable = false
        config.barCollapsingEnabled = true
        
        let safariVC = SFSafariViewController(url: url, configuration: config)
        safariVC.preferredControlTintColor = .systemBlue
        return safariVC
    }
    
    func updateUIViewController(_ uiViewController: SFSafariViewController, context: Context) {}
}

// View modifier to present Safari
struct SafariViewModifier: ViewModifier {
    @Binding var isPresented: Bool
    let url: URL?
    
    func body(content: Content) -> some View {
        content
            .sheet(isPresented: $isPresented) {
                if let url = url {
                    SafariView(url: url)
                        .ignoresSafeArea()
                }
            }
    }
}

extension View {
    func safariSheet(isPresented: Binding<Bool>, url: URL?) -> some View {
        modifier(SafariViewModifier(isPresented: isPresented, url: url))
    }
}
