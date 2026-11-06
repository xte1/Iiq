//
//  AutoInstallBanner.swift
//  i Cerf
//

import SwiftUI

struct AutoInstallBanner: View {
	@ObservedObject private var _installer = AutoInstaller.shared
	@State private var _progress: Double = 0
	private let _timer = Timer.publish(every: 0.3, on: .main, in: .common).autoconnect()
	
	var body: some View {
		Group {
			if _installer.stage != .idle {
				HStack(spacing: 12) {
					_icon
					Text(_text)
						.font(.subheadline.weight(.semibold))
						.lineLimit(2)
					Spacer(minLength: 0)
				}
				.padding(.horizontal, 16)
				.padding(.vertical, 12)
				.background(.ultraThinMaterial)
				.clipShape(RoundedRectangle(cornerRadius: 20, style: .continuous))
				.shadow(color: Color.black.opacity(0.15), radius: 8, x: 0, y: 3)
				.padding(.horizontal, 16)
				.padding(.top, 6)
				.transition(.move(edge: .top).combined(with: .opacity))
			}
		}
		.animation(.smooth, value: _installer.stage)
		.onReceive(_timer) { _ in
			if let id = _installer.currentID, let download = DownloadManager.shared.getDownload(by: id) {
				_progress = download.overallProgress
			}
			_installer.checkCancelled()
		}
	}
	
	@ViewBuilder
	private var _icon: some View {
		switch _installer.stage {
		case .downloading:
			ProgressView(value: _progress).progressViewStyle(.circular)
		case .signing:
			ProgressView()
		case .installing:
			Image(systemName: "checkmark.circle.fill").foregroundStyle(.green)
		case .failed:
			Image(systemName: "exclamationmark.triangle.fill").foregroundStyle(.orange)
		case .idle:
			EmptyView()
		}
	}
	
	private var _text: String {
		let name = _installer.appName
		switch _installer.stage {
		case .downloading: return "جاري تنزيل \(name)… \(Int(_progress * 100))%"
		case .signing: return "جاري توقيع \(name)…"
		case .installing: return "\(name) جاهز للتثبيت"
		case .failed(let message): return "فشل: \(message)"
		case .idle: return ""
		}
	}
}
