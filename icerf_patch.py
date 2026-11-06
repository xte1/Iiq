#!/usr/bin/env python3
# i Cerf patch: يطبّق تعديلات i Cerf على كود Feather
import os
import re

def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, "w", encoding="utf-8").write(text)

def edit(path, pairs):
    s = open(path, encoding="utf-8").read()
    for old, new in pairs:
        pattern = r"\s+".join(re.escape(t) for t in old.split())
        assert len(re.findall(pattern, s)) == 1, "pattern not found in " + path + ": " + old[:60]
        s = re.sub(pattern, lambda m: new.strip(), s, count=1)
    open(path, "w", encoding="utf-8").write(s)

write('Feather/Backend/Observable/AutoInstaller.swift', r'''//
//  AutoInstaller.swift
//  i Cerf
//
//  تنزيل ثم توقيع ثم تثبيت بضغطة واحدة
//

import Foundation
import CoreData
import SwiftUI

final class AutoInstaller: ObservableObject {
	static let shared = AutoInstaller()
	/// يُضاف لنهاية المعرّف حتى لا يتعارض مع تطبيق مشابه
	static let idSuffix = "icerf"
	
	enum Stage: Equatable {
		case idle
		case downloading
		case signing
		case installing
		case failed(String)
	}
	
	@Published var stage: Stage = .idle
	@Published var appName: String = ""
	@Published var currentID: String?
	@Published var installApp: AnyApp?
	
	private var _pendingID: String?
	
	var isBusy: Bool {
		stage == .downloading || stage == .signing
	}
	
	// MARK: Start
	func install(from url: URL, id: String, name: String, provenance: SourceAppProvenance?) {
		guard !isBusy else {
			UIAlertController.showAlertWithOk(title: "i Cerf", message: "هناك تطبيق قيد التنزيل حالياً، انتظر حتى ينتهي.")
			return
		}
		
		guard !Storage.shared.getAllCertificates().isEmpty else {
			UIAlertController.showAlertWithOk(
				title: "لا توجد شهادة",
				message: "اذهب إلى الإعدادات ثم الشهادات وأضف شهادة صالحة أولاً."
			)
			return
		}
		
		appName = name
		currentID = id
		_pendingID = id
		stage = .downloading
		
		_ = DownloadManager.shared.startDownload(from: url, id: id, sourceProvenance: provenance)
	}
	
	// MARK: Hooks
	/// تُستدعى من DownloadManager بعد انتهاء التنزيل واستيراد الملف
	func importFinished(downloadID: String, error: Error?) {
		guard _pendingID == downloadID else { return }
		_pendingID = nil
		
		if let error {
			_fail(error.localizedDescription)
			return
		}
		
		let request: NSFetchRequest<Imported> = Imported.fetchRequest()
		request.sortDescriptors = [NSSortDescriptor(keyPath: \Imported.date, ascending: false)]
		request.fetchLimit = 1
		
		guard let imported = try? Storage.shared.context.fetch(request).first else {
			_fail("تعذر العثور على الملف بعد التنزيل.")
			return
		}
		
		_sign(imported)
	}
	
	/// تُستدعى بشكل دوري لاكتشاف إلغاء التنزيل أو فشله
	func checkCancelled() {
		guard
			stage == .downloading,
			let pending = _pendingID,
			DownloadManager.shared.getDownload(by: pending) == nil
		else { return }
		
		_pendingID = nil
		_fail("تم إلغاء التنزيل أو فشل.")
	}
	
	func finish() {
		installApp = nil
		stage = .idle
		currentID = nil
	}
	
	// MARK: Private
	private func _sign(_ app: Imported) {
		stage = .signing
		
		var options = OptionsManager.shared.options
		if
			let current = app.identifier,
			!current.hasSuffix(".\(Self.idSuffix)")
		{
			options.appIdentifier = "\(current).\(Self.idSuffix)"
		}
		
		let storedIndex = UserDefaults.standard.integer(forKey: "feather.selectedCert")
		let certificate = Storage.shared.getCertificate(for: storedIndex)
			?? Storage.shared.getAllCertificates().first
		
		FR.signPackageFile(
			app,
			using: options,
			icon: nil,
			certificate: certificate
		) { [weak self] error in
			guard let self else { return }
			
			if let error {
				self._fail(error.localizedDescription)
				return
			}
			
			let request: NSFetchRequest<Signed> = Signed.fetchRequest()
			request.sortDescriptors = [NSSortDescriptor(keyPath: \Signed.date, ascending: false)]
			request.fetchLimit = 1
			
			guard let signed = try? Storage.shared.context.fetch(request).first else {
				self._fail("تعذر العثور على التطبيق الموقّع.")
				return
			}
			
			// حذف النسخة غير الموقّعة لتوفير المساحة
			Storage.shared.deleteApp(for: app)
			
			self.stage = .installing
			self.installApp = AnyApp(base: signed)
		}
	}
	
	private func _fail(_ message: String) {
		DispatchQueue.main.async {
			self.stage = .failed(message)
			DispatchQueue.main.asyncAfter(deadline: .now() + 5) {
				if case .failed = self.stage { self.stage = .idle }
			}
		}
	}
}
''')

write('Feather/Views/Common/AutoInstallBanner.swift', r'''//
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
''')

write('Feather/Views/Common/SplashView.swift', r'''//
//  SplashView.swift
//  i Cerf
//

import SwiftUI

struct SplashView: View {
	var body: some View {
		ZStack {
			Color(.systemBackground).ignoresSafeArea()
			
			Image("Glyph")
				.resizable()
				.scaledToFit()
				.frame(width: 280, height: 300)
			
			VStack {
				Spacer()
				Text("i Cerf")
					.font(.title2.bold())
					.foregroundStyle(.secondary)
					.padding(.bottom, 48)
			}
		}
	}
}
''')

write('Feather/Views/Settings/About/AboutView.swift', r'''//
//  AboutView.swift
//  i Cerf
//

import SwiftUI
import NimbleViews

// MARK: - View
struct AboutView: View {
	private let _contacts: [(title: String, handle: String, icon: String, url: String)] = [
		("Instagram", "eng_azawy", "camera.circle.fill", "https://instagram.com/eng_azawy"),
		("Telegram", "bavarite", "paperplane.circle.fill", "https://t.me/bavarite"),
		("قناتنا على تيليجرام", "iCERF_iQ", "megaphone.fill", "https://t.me/iCERF_iQ"),
		("TikTok", "eyesiq", "music.note", "https://www.tiktok.com/@eyesiq"),
		("الموقع", "icerf.netlify.app", "globe", "https://icerf.netlify.app")
	]
	
	// MARK: Body
	var body: some View {
		NBList(.localized("About")) {
			Section {
				VStack {
					Image("Glyph")
						.resizable()
						.scaledToFit()
						.frame(height: 110)
					
					Text("i Cerf")
						.font(.largeTitle)
						.bold()
						.foregroundStyle(Color.accentColor)
					
					HStack(spacing: 4) {
						Text(.localized("Version"))
						Text(Bundle.main.version)
					}
					.font(.footnote)
					.foregroundStyle(.secondary)
				}
			}
			.frame(maxWidth: .infinity)
			.listRowBackground(EmptyView())
			
			NBSection("المطور") {
				ForEach(_contacts, id: \.url) { contact in
					Button {
						UIApplication.open(contact.url)
					} label: {
						HStack(spacing: 14) {
							Image(systemName: contact.icon)
								.font(.system(size: 26))
								.frame(width: 34)
								.foregroundStyle(Color.accentColor)
							VStack(alignment: .leading, spacing: 2) {
								Text(contact.title)
									.foregroundStyle(.primary)
								Text(contact.handle)
									.font(.footnote)
									.foregroundStyle(.secondary)
							}
							Spacer()
							Image(systemName: "arrow.up.right")
								.foregroundColor(.secondary.opacity(0.65))
						}
					}
				}
			}
		}
	}
}
''')

write('Feather/Views/Settings/SettingsView.swift', r'''//
//  SettingsView.swift
//  Feather
//
//  Created by samara on 10.04.2025.
//

import SwiftUI
import NimbleViews
import UIKit
import Darwin
import IDeviceSwift

// MARK: - View
struct SettingsView: View {
	@AppStorage("feather.selectedCert") private var _storedSelectedCert: Int = 0
	@State private var _currentIcon: String? = UIApplication.shared.alternateIconName
	
	// MARK: Fetch
	@FetchRequest(
		entity: CertificatePair.entity(),
		sortDescriptors: [NSSortDescriptor(keyPath: \CertificatePair.date, ascending: false)],
		animation: .snappy
	) private var _certificates: FetchedResults<CertificatePair>
	
	private var selectedCertificate: CertificatePair? {
		guard
			_storedSelectedCert >= 0,
			_storedSelectedCert < _certificates.count
		else {
			return nil
		}
		return _certificates[_storedSelectedCert]
	}

    
	private let _siteUrl = "https://icerf.netlify.app"
	private let _telegramUrl = "https://t.me/iCERF_iQ"
    
	// MARK: Body
	var body: some View {
		NBNavigationView(.localized("Settings")) {
			Form {
                
				_feedback()
                
				Section {
					NavigationLink(destination: AppearanceView()) {
						Label(.localized("Appearance"), systemImage: "paintbrush")
					}
					NavigationLink(destination: AppIconView(currentIcon: $_currentIcon)) {
						Label(.localized("App Icon"), systemImage: "app.badge")
					}
				}
                
				NBSection(.localized("Certificates")) {
                    
					if let cert = selectedCertificate {
						CertificatesCellView(cert: cert)
					} else {
						Text(.localized("No Certificate"))
							.font(.footnote)
							.foregroundColor(.disabled())
					}
					NavigationLink(destination: CertificatesView()) {
						Label(.localized("Certificates"), systemImage: "checkmark.seal")
					}
                 
				} footer: {
					Text(.localized("Add and manage certificates used for signing applications."))
				}
                
				NBSection(.localized("Features")) {
					NavigationLink(destination: ConfigurationView()) {
						Label(.localized("Signing Options"), systemImage: "signature")
					}
					NavigationLink(destination: ArchiveView()) {
						Label(.localized("Archive & Compression"), systemImage: "archivebox")
					}
					NavigationLink(destination: InstallationView()) {
						Label(.localized("Installation"), systemImage: "arrow.down.circle")
					}
				} footer: {
					Text(.localized("Configure the apps way of installing, its zip compression levels, and custom modifications to apps."))
				}
                
				_directories()
                
				Section {
					NavigationLink(destination: ResetView()) {
						Label(.localized("Reset"), systemImage: "trash")
					}
				} footer: {
					Text(.localized("Reset the applications sources, certificates, apps, and general contents."))
				}
			}
		}
	}
}

// MARK: - View extension
extension SettingsView {
	@ViewBuilder
	private func _feedback() -> some View {
		Section {
			NavigationLink(destination: AboutView()) {
				Label {
					Text(verbatim: .localized("About %@", arguments: Bundle.main.name))
				} icon: {
					FRAppIconView(size: 23)
				}
			}
            
			Button("قناتنا على تيليجرام", systemImage: "paperplane") {
				UIApplication.open(_telegramUrl)
			}
			Button("الموقع الرسمي", systemImage: "safari") {
				UIApplication.open(_siteUrl)
			}
		} footer: {
			Text("إذا واجهتك أي مشكلة في التطبيق تواصل معنا عبر قناتنا على تيليجرام.")
		}
	}
    
	@ViewBuilder
	private func _directories() -> some View {
		NBSection(.localized("Misc")) {
			Button(.localized("Open Documents"), systemImage: "folder") {
				UIApplication.open(URL.documentsDirectory.toSharedDocumentsURL()!)
			}
			Button(.localized("Open Archives"), systemImage: "folder") {
				UIApplication.open(FileManager.default.archives.toSharedDocumentsURL()!)
			}
			Button(.localized("Open Certificates"), systemImage: "folder") {
				UIApplication.open(FileManager.default.certificates.toSharedDocumentsURL()!)
			}
		} footer: {
			Text(.localized("All of the apps files are contained in the documents directory, here are some quick links to these."))
		}
	}
}
''')

write('Feather/Views/Today/TodayView.swift', r'''//
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
''')

edit('Feather/Backend/Observable/DownloadManager.swift', [
(r'''			}
			
			DispatchQueue.main.async {
				if let index = DownloadManager.shared.getDownloadIndex(by: dl.id) {
''', r'''			}
			
			AutoInstaller.shared.importFinished(downloadID: dl.id, error: err)
			
			DispatchQueue.main.async {
				if let index = DownloadManager.shared.getDownloadIndex(by: dl.id) {
'''),
])

edit('Feather/FeatherApp.swift', [
(r'''	
	let heartbeat = HeartbeatManager.shared
	
	@StateObject var downloadManager = DownloadManager.shared
''', r'''	
	let heartbeat = HeartbeatManager.shared
	@State private var _showSplash = true
	@StateObject private var _autoInstaller = AutoInstaller.shared
	
	@StateObject var downloadManager = DownloadManager.shared
'''),
(r'''				UIApplication.topViewController()?.view.window?.tintColor = UIColor(Color(hex: UserDefaults.standard.string(forKey: "Feather.userTintColor") ?? "#848ef9"))
			}
		}
	}
''', r'''				UIApplication.topViewController()?.view.window?.tintColor = UIColor(Color(hex: UserDefaults.standard.string(forKey: "Feather.userTintColor") ?? "#848ef9"))
			}
			.overlay(alignment: .top) {
				AutoInstallBanner()
			}
			.sheet(item: $_autoInstaller.installApp, onDismiss: {
				AutoInstaller.shared.finish()
			}) { app in
				InstallPreviewView(app: app.base, isSharing: app.archive)
					.presentationDetents([.height(200)])
					.presentationDragIndicator(.visible)
			}
			.overlay {
				if _showSplash {
					SplashView()
						.transition(.opacity)
				}
			}
			.task {
				try? await Task.sleep(nanoseconds: 2_000_000_000)
				withAnimation(.easeOut(duration: 0.4)) {
					_showSplash = false
				}
				FeatherApp.addDefaultSourceIfNeeded()
			}
		}
	}
	
	/// السورس الافتراضي — يُضاف مرة واحدة عند أول تشغيل
	static func addDefaultSourceIfNeeded() {
		let key = "icerf.didAddDefaultSource"
		guard !UserDefaults.standard.bool(forKey: key) else { return }
		FR.handleSource("https://raw.githubusercontent.com/AbdTench/SwiftSource/refs/heads/main/My%20Source") {
			UserDefaults.standard.set(true, forKey: key)
		}
	}
'''),
(r'''		didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]? = nil
	) -> Bool {
		_createPipeline()
		_createDocumentsDirectories()
''', r'''		didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]? = nil
	) -> Bool {
		UserDefaults.standard.register(defaults: ["Feather.serverMethod": 1])
		_createPipeline()
		_createDocumentsDirectories()
'''),
])

edit('Feather/Views/Library/Install/InstallPreviewView.swift', [
(r'''	@AppStorage("Feather.useShareSheetForArchiving") private var _useShareSheet: Bool = false
	@AppStorage("Feather.installationMethod") private var _installationMethod: Int = 0
	@AppStorage("Feather.serverMethod") private var _serverMethod: Int = 0
	@State private var _isWebviewPresenting = false
	@State private var progressTask: Task<Void, Never>?
''', r'''	@AppStorage("Feather.useShareSheetForArchiving") private var _useShareSheet: Bool = false
	@AppStorage("Feather.installationMethod") private var _installationMethod: Int = 0
	@AppStorage("Feather.serverMethod") private var _serverMethod: Int = 1
	@State private var _isWebviewPresenting = false
	@State private var progressTask: Task<Void, Never>?
'''),
])

edit('Feather/Views/Settings/App Icon/AppIconView.swift', [
(r'''	// dont translate
	var sections: [String: [AltIcon]] = [
		"Main": [
			AltIcon(displayName: "Feather", author: "Samara", key: nil),
			AltIcon(displayName: "Feather (macOS)", author: "Samara", key: "V2Mac"),
			AltIcon(displayName: "Feather v1", author: "Samara", key: "V1"),
			AltIcon(displayName: "Feather v1 (macOS)", author: "Samara", key: "V1Mac"),
			AltIcon(displayName: "Feather v0", author: "Samara", key: "V0"),
			AltIcon(displayName: "Feather Donor", author: "Samara", key: "Donor")
		],
		"Wingio": [
			AltIcon(displayName: "Feather", author: "Wingio", key: "Wing"),
		]
	]
''', r'''	// dont translate
	var sections: [String: [AltIcon]] = [
		"i Cerf": [
			AltIcon(displayName: "i Cerf", author: "i Cerf", key: nil)
		]
	]
'''),
])

edit('Feather/Views/Settings/Installation/Server & SSL/ServerView.swift', [
(r'''struct ServerView: View {
	@AppStorage("Feather.ipFix") private var _ipFix: Bool = false
	@AppStorage("Feather.serverMethod") private var _serverMethod: Int = 0
	private let _serverMethods: [String] = [.localized("Fully Local"), .localized("Semi Local")]
	
''', r'''struct ServerView: View {
	@AppStorage("Feather.ipFix") private var _ipFix: Bool = false
	@AppStorage("Feather.serverMethod") private var _serverMethod: Int = 1
	private let _serverMethods: [String] = [.localized("Fully Local"), .localized("Semi Local")]
	
'''),
])

edit('Feather/Views/Sources/Apps/Detail/VersionHistoryView.swift', [
(r'''						if let downloadURL = version.downloadURL {
							Button {
								_ = DownloadManager.shared.startDownload(
									from: downloadURL,
									id: app.currentUniqueId,
''', r'''						if let downloadURL = version.downloadURL {
							Button {
								AutoInstaller.shared.install(
									from: downloadURL,
									id: app.currentUniqueId,
'''),
(r'''									from: downloadURL,
									id: app.currentUniqueId,
									sourceProvenance: SourceAppProvenance(
										sourceURL: sourceURL,
										repository: source,
''', r'''									from: downloadURL,
									id: app.currentUniqueId,
									name: app.currentName,
									provenance: SourceAppProvenance(
										sourceURL: sourceURL,
										repository: source,
'''),
])

edit('Feather/Views/Sources/Apps/DownloadButtonView.swift', [
(r'''				Button {
					if let url = app.currentDownloadUrl {
						_ = downloadManager.startDownload(
							from: url,
							id: app.currentUniqueId,
''', r'''				Button {
					if let url = app.currentDownloadUrl {
						AutoInstaller.shared.install(
							from: url,
							id: app.currentUniqueId,
'''),
(r'''							from: url,
							id: app.currentUniqueId,
							sourceProvenance: _sourceProvenance()
						)
					}
''', r'''							from: url,
							id: app.currentUniqueId,
							name: app.currentName,
							provenance: _sourceProvenance()
						)
					}
'''),
(r'''					}
				} label: {
					Text(.localized("Get"))
						.lineLimit(0)
						.font(.headline.bold())
''', r'''					}
				} label: {
					Text("تنزيل")
						.lineLimit(0)
						.font(.headline.bold())
'''),
])

edit('Feather/Views/Sources/Apps/UIKit/SourceAppsTableRepresentableView.swift', [
(r'''				children: self._contextActions(for: entry.app, with: { version, url in
					if let url {
						_ = DownloadManager.shared.startDownload(
							from: url,
							id: entry.app.currentUniqueId,
''', r'''				children: self._contextActions(for: entry.app, with: { version, url in
					if let url {
						AutoInstaller.shared.install(
							from: url,
							id: entry.app.currentUniqueId,
'''),
(r'''							from: url,
							id: entry.app.currentUniqueId,
							sourceProvenance: SourceAppProvenance(
								sourceURL: entry.sourceURL,
								repository: entry.source,
''', r'''							from: url,
							id: entry.app.currentUniqueId,
							name: entry.app.currentName,
							provenance: SourceAppProvenance(
								sourceURL: entry.sourceURL,
								repository: entry.source,
'''),
])

edit('Feather/Views/Sources/SourcesAddView.swift', [
(r'''	@State var recommendedSourcesData: [(url: URL, data: ASRepository)] = []
	let recommendedSources: [URL] = [
		"https://raw.githubusercontent.com/claration/Feather/refs/heads/main/app-repo.json",
		"https://raw.githubusercontent.com/Aidoku/Aidoku/altstore/apps.json",
		"https://github.com/chachillie/Flycast-iOS/raw/main/flycast-ios.json",
''', r'''	@State var recommendedSourcesData: [(url: URL, data: ASRepository)] = []
	let recommendedSources: [URL] = [
		"https://raw.githubusercontent.com/AbdTench/SwiftSource/refs/heads/main/My%20Source",
		"https://raw.githubusercontent.com/Aidoku/Aidoku/altstore/apps.json",
		"https://github.com/chachillie/Flycast-iOS/raw/main/flycast-ios.json",
'''),
(r'''						}
					} footer: {
						Text(.localized("Open an [issue](https://github.com/claration/Feather/issues) on GitHub if you want your source to be featured."))
					}
				}
''', r'''						}
					} footer: {
						Text("لإضافة سورسك هنا تواصل معنا عبر [قناتنا على تيليجرام](https://t.me/iCERF_iQ).")
					}
				}
'''),
])

edit('Feather/Views/Sources/SourcesView.swift', [
(r'''struct SourcesView: View {
	@Environment(\.horizontalSizeClass) private var horizontalSizeClass
	#if !NIGHTLY && !DEBUG
		@AppStorage("Feather.shouldStar") private var _shouldStar: Int = 0
	#endif
	@StateObject var viewModel = SourcesViewModel.shared
	@State private var _isAddingPresenting = false
''', r'''struct SourcesView: View {
	@Environment(\.horizontalSizeClass) private var horizontalSizeClass
	@StateObject var viewModel = SourcesViewModel.shared
	@State private var _isAddingPresenting = false
'''),
(r'''	// MARK: Body
	var body: some View {
		NBNavigationView(.localized("Sources")) {
			NBListAdaptable {
				if !_filteredSources.isEmpty {
''', r'''	// MARK: Body
	var body: some View {
		NBNavigationView("المتجر") {
			NBListAdaptable {
				if !_filteredSources.isEmpty {
'''),
(r'''			await viewModel.fetchSources(_sources)
		}
		#if !NIGHTLY && !DEBUG
		.onAppear {
				guard _shouldStar < 6 else { return }; _shouldStar += 1
				guard _shouldStar == 6 else { return }
			
				let github = UIAlertAction(title: "GitHub", style: .default) { _ in
					UIApplication.open("https://github.com/khcrysalis/Feather")
				}
			
				let cancel = UIAlertAction(title: .localized("Dismiss"), style: .cancel)
			
				UIAlertController.showAlert(
					title: .localized("Enjoying %@?", arguments: Bundle.main.name),
					message: .localized("Go to our GitHub and give us a star!"),
					actions: [github, cancel]
				)
			}
		#endif
	}
}
''', r'''			await viewModel.fetchSources(_sources)
		}
	}
}
'''),
])

edit('Feather/Views/TabView/Bars/TabbarView.swift', [
(r'''
struct TabbarView: View {
	@State private var selectedTab: TabEnum = .sources

	var body: some View {
''', r'''
struct TabbarView: View {
	@State private var selectedTab: TabEnum = .today

	var body: some View {
'''),
])

edit('Feather/Views/TabView/TabEnum.swift', [
(r'''
enum TabEnum: String, CaseIterable, Hashable {
	case sources
	case library
''', r'''
enum TabEnum: String, CaseIterable, Hashable {
	case today
	case sources
	case library
'''),
(r'''	var title: String {
		switch self {
		case .sources:     	return .localized("Sources")
		case .library: 		return .localized("Library")
		case .settings: 	return .localized("Settings")
''', r'''	var title: String {
		switch self {
		case .today:       	return "اليوم"
		case .sources:     	return "المتجر"
		case .library: 		return .localized("Library")
		case .settings: 	return .localized("Settings")
'''),
(r'''	var icon: String {
		switch self {
		case .sources: 		return "globe.desk"
		case .library: 		return "square.grid.2x2"
''', r'''	var icon: String {
		switch self {
		case .today: 		return "newspaper"
		case .sources: 		return "globe.desk"
		case .library: 		return "square.grid.2x2"
'''),
(r'''	static func view(for tab: TabEnum) -> some View {
		switch tab {
		case .sources: SourcesView()
		case .library: LibraryView()
''', r'''	static func view(for tab: TabEnum) -> some View {
		switch tab {
		case .today: TodayView()
		case .sources: SourcesView()
		case .library: LibraryView()
'''),
(r'''	static var defaultTabs: [TabEnum] {
		return [
			.sources,
			.library,
''', r'''	static var defaultTabs: [TabEnum] {
		return [
			.today,
			.sources,
			.library,
'''),
])

print('i Cerf patch applied')
