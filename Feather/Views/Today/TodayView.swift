//
//  TodayView.swift
//  i Cerf
//
//  الصفحة الرئيسية بتصميم بطاقات كبيرة
//

import SwiftUI
import CoreData
import AltSourceKit
import NukeUI

struct TodayView: View {
	@StateObject private var _viewModel = SourcesViewModel.shared
	
	@FetchRequest(
		entity: AltSource.entity(),
		sortDescriptors: [NSSortDescriptor(keyPath: \AltSource.name, ascending: true)],
		animation: .snappy
	) private var _sources: FetchedResults<AltSource>
	
	private struct Entry: Identifiable {
		let id: String
		let sourceURL: URL?
		let source: ASRepository
		let app: ASRepository.App
	}
	
	private var _entries: [Entry] {
		var result: [Entry] = []
		for source in _sources {
			guard let repo = _viewModel.sources[source] else { continue }
			for app in repo.apps {
				result.append(Entry(
					id: "\(source.identifier ?? "")-\(app.currentUniqueId)",
					sourceURL: source.sourceURL,
					source: repo,
					app: app
				))
			}
		}
		return result
	}
	
	var body: some View {
		NavigationView {
			ScrollView {
				LazyVStack(spacing: 22) {
					_header
					
					ForEach(_entries) { entry in
						TodayCardView(sourceURL: entry.sourceURL, source: entry.source, app: entry.app)
					}
					
					if _entries.isEmpty {
						VStack(spacing: 10) {
							ProgressView()
							Text("جاري تحميل التطبيقات…")
								.font(.footnote)
								.foregroundStyle(.secondary)
						}
						.padding(.top, 80)
					}
				}
				.padding(.horizontal)
				.padding(.bottom, 24)
			}
			.navigationBarHidden(true)
			.task { await _viewModel.fetchSources(_sources) }
			.refreshable { await _viewModel.fetchSources(_sources, refresh: true) }
		}
		.navigationViewStyle(.stack)
	}
	
	private var _header: some View {
		HStack {
			Text("i Cerf")
				.font(.title.bold())
				.padding(.horizontal, 22)
				.padding(.vertical, 8)
				.background(.ultraThinMaterial)
				.clipShape(Capsule())
			
			Spacer()
			
			Image("Glyph")
				.resizable()
				.scaledToFit()
				.frame(width: 52, height: 52)
				.background(.ultraThinMaterial)
				.clipShape(Circle())
		}
		.padding(.top, 8)
	}
}

// MARK: - Card
struct TodayCardView: View {
	let sourceURL: URL?
	let source: ASRepository
	let app: ASRepository.App
	
	private var _tint: Color {
		app.tintColor ?? source.tintColor ?? Color.accentColor
	}
	
	private var _screenshot: URL? {
		app.screenshots?.iPhone?.first ?? app.screenshotURLs?.first
	}
	
	var body: some View {
		ZStack(alignment: .bottom) {
			_background
			
			LinearGradient(
				colors: [.clear, Color.black.opacity(0.6)],
				startPoint: .center,
				endPoint: .bottom
			)
			
			VStack(alignment: .leading, spacing: 6) {
				Spacer()
				
				Text(app.currentName)
					.font(.title.bold())
					.foregroundColor(.white)
					.lineLimit(2)
					.multilineTextAlignment(.leading)
				
				if let text = app.subtitle ?? app.localizedDescription {
					Text(text)
						.font(.subheadline)
						.foregroundColor(.white.opacity(0.88))
						.lineLimit(2)
						.multilineTextAlignment(.leading)
				}
				
				HStack(spacing: 12) {
					FRIconView(url: app.iconURL, size: 50)
					
					VStack(alignment: .leading, spacing: 2) {
						Text(app.currentName)
							.font(.subheadline.bold())
							.lineLimit(1)
						Text([app.developer, app.currentVersion].compactMap { $0 }.joined(separator: " • "))
							.font(.caption)
							.foregroundStyle(.secondary)
							.lineLimit(1)
					}
					
					Spacer(minLength: 4)
					
					DownloadButtonView(sourceURL: sourceURL, source: source, app: app)
				}
				.padding(12)
				.background(.ultraThinMaterial)
				.clipShape(RoundedRectangle(cornerRadius: 20, style: .continuous))
				.padding(.top, 6)
			}
			.padding(14)
		}
		.overlay(alignment: .topTrailing) {
			Text("متوفر الآن")
				.font(.caption.bold())
				.padding(.horizontal, 12)
				.padding(.vertical, 7)
				.background(.ultraThinMaterial)
				.clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
				.padding(14)
		}
		.frame(height: 460)
		.clipShape(RoundedRectangle(cornerRadius: 28, style: .continuous))
		.shadow(color: Color.black.opacity(0.18), radius: 10, x: 0, y: 5)
	}
	
	@ViewBuilder
	private var _background: some View {
		ZStack {
			LinearGradient(
				colors: [_tint, _tint.opacity(0.45)],
				startPoint: .topLeading,
				endPoint: .bottomTrailing
			)
			
			if let shot = _screenshot {
				LazyImage(url: shot) { state in
					if let image = state.image {
						image.resizable().scaledToFill()
					}
				}
			} else {
				VStack {
					FRIconView(url: app.iconURL, size: 150)
						.shadow(color: Color.black.opacity(0.25), radius: 14, x: 0, y: 8)
					Spacer()
				}
				.padding(.top, 70)
			}
		}
		.clipped()
	}
}

/// أيقونة تطبيق بسيطة من رابط
struct FRIconView: View {
	let url: URL?
	let size: CGFloat
	
	var body: some View {
		LazyImage(url: url) { state in
			if let image = state.image {
				image.resizable().scaledToFill()
			} else {
				Color.gray.opacity(0.25)
			}
		}
		.frame(width: size, height: size)
		.clipShape(RoundedRectangle(cornerRadius: size * 0.225, style: .continuous))
		.overlay(
			RoundedRectangle(cornerRadius: size * 0.225, style: .continuous)
				.stroke(Color.gray.opacity(0.25), lineWidth: 0.5)
		)
	}
}
