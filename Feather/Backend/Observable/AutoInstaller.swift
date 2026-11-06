//
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
