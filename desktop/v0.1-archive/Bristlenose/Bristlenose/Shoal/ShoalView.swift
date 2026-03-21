import SpriteKit
import SwiftUI

/// SwiftUI wrapper for the typographic shoal SpriteKit scene.
///
/// Displays the flocking word animation with a soft gradient dissolve
/// at the bottom edge (no hard boundary between the shoal and the log area).
struct ShoalView: View {
    @Binding var phase: ShoalPhase

    /// Set to true when the pipeline fails — triggers the death animation.
    @Binding var failed: Bool

    @State private var scene: ShoalScene = {
        let s = ShoalScene(size: CGSize(width: 480, height: 300))
        s.scaleMode = .resizeFill
        return s
    }()

    @State private var selectedBehaviorIndex = 0

    var body: some View {
        ZStack {
            // SpriteKit scene
            SpriteView(scene: scene, options: [.allowsTransparency])

            // Gradient dissolve at bottom edge
            VStack {
                Spacer()
                LinearGradient(
                    colors: [.clear, Color(nsColor: .windowBackgroundColor)],
                    startPoint: UnitPoint(x: 0.5, y: 0.0),
                    endPoint: UnitPoint(x: 0.5, y: 1.0)
                )
                .frame(height: 30)
            }
            .allowsHitTesting(false)

            #if DEBUG
            // Debug behaviour picker — top right corner
            VStack {
                HStack {
                    Spacer()
                    Picker("", selection: $selectedBehaviorIndex) {
                        ForEach(allFlockingBehaviors.indices, id: \.self) { index in
                            Text(allFlockingBehaviors[index].name).tag(index)
                        }
                    }
                    .pickerStyle(.menu)
                    .fixedSize()
                    .padding(6)
                    .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 6))
                    .padding(8)
                }
                Spacer()
            }
            #endif
        }
        .onChange(of: phase) { oldPhase, newPhase in
            if newPhase == .early, oldPhase != .early {
                scene.reset()
            } else {
                scene.advanceToPhase(newPhase)
            }
        }
        .onChange(of: failed) { _, hasFailed in
            if hasFailed {
                scene.die()
            }
        }
        #if DEBUG
        .onChange(of: selectedBehaviorIndex) { _, newIndex in
            scene.behavior = allFlockingBehaviors[newIndex]
        }
        #endif
    }
}
