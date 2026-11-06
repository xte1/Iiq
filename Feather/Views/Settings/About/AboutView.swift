//
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
