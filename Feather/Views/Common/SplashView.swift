//
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
