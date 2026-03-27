import SwiftUI

/// A 10x10 grid of curated SF Symbols for choosing a project icon.
///
/// The top-left icon is the default (`circle.fill`). Icons flow from abstract/geometric
/// through nature, animals, objects, creative, sport, to science/learning.
/// All symbols are from SF Symbols 6 (macOS 15.0+, our deployment target).
///
/// Entry points: context menu "Choose Icon..." on project rows, and (future)
/// Get Info panel, project dashboard, Project menu bar.
struct IconPickerPopover: View {

    let selectedIcon: String?
    let onSelect: (String?) -> Void

    /// The default icon shown when no custom icon is set.
    static let defaultIcon = "circle.fill"

    /// 100 curated SF Symbols — identity marks, not system chrome.
    /// Position [0] is the default. Grid flows abstract → figurative.
    static let palette: [(name: String, label: String)] = [
        // Row 1 — Geometric / Abstract
        ("circle.fill", "Circle"),
        ("square.fill", "Square"),
        ("triangle.fill", "Triangle"),
        ("diamond.fill", "Diamond"),
        ("hexagon.fill", "Hexagon"),
        ("octagon.fill", "Octagon"),
        ("seal.fill", "Seal"),
        ("shield.fill", "Shield"),
        ("heart.fill", "Heart"),
        ("star.fill", "Star"),

        // Row 2 — Stars / Sparkle / Energy
        ("staroflife.fill", "Star of Life"),
        ("sparkle", "Sparkle"),
        ("sparkles", "Sparkles"),
        ("asterisk", "Asterisk"),
        ("bolt.fill", "Bolt"),
        ("bolt.circle", "Bolt Circle"),
        ("flame.fill", "Flame"),
        ("light.max", "Light"),
        ("rays", "Rays"),
        ("wand.and.rays", "Wand and Rays"),

        // Row 3 — Water / Weather / Sky
        ("drop.fill", "Drop"),
        ("cloud.fill", "Cloud"),
        ("cloud.rain.fill", "Rain"),
        ("cloud.bolt.fill", "Storm"),
        ("snowflake", "Snowflake"),
        ("wind", "Wind"),
        ("tornado", "Tornado"),
        ("moon.fill", "Moon"),
        ("moon.stars.fill", "Moon and Stars"),
        ("sun.max.fill", "Sun"),

        // Row 4 — Nature / Earth
        ("leaf.fill", "Leaf"),
        ("tree.fill", "Tree"),
        ("mountain.2.fill", "Mountains"),
        ("globe.europe.africa.fill", "Globe Europe Africa"),
        ("globe.americas.fill", "Globe Americas"),
        ("globe.asia.australia.fill", "Globe Asia Australia"),
        ("atom", "Atom"),
        ("hurricane", "Hurricane"),
        ("allergens", "Allergens"),
        ("fossil.shell.fill", "Fossil"),

        // Row 5 — Animals
        ("tortoise.fill", "Tortoise"),
        ("hare.fill", "Hare"),
        ("bird.fill", "Bird"),
        ("fish.fill", "Fish"),
        ("ant.fill", "Ant"),
        ("ladybug.fill", "Ladybug"),
        ("cat.fill", "Cat"),
        ("dog.fill", "Dog"),
        ("pawprint.fill", "Paw Print"),
        ("lizard.fill", "Lizard"),

        // Row 6 — Food / Drink / Home
        ("cup.and.saucer.fill", "Cup and Saucer"),
        ("fork.knife", "Fork and Knife"),
        ("carrot.fill", "Carrot"),
        ("birthday.cake.fill", "Birthday Cake"),
        ("takeoutbag.and.cup.and.straw.fill", "Takeout"),
        ("house.fill", "House"),
        ("building.2.fill", "Building"),
        ("tent.fill", "Tent"),
        ("lamp.desk.fill", "Desk Lamp"),
        ("washer.fill", "Washer"),

        // Row 7 — Objects / Tools
        ("key.fill", "Key"),
        ("lock.fill", "Lock"),
        ("gift.fill", "Gift"),
        ("hourglass", "Hourglass"),
        ("dice.fill", "Dice"),
        ("puzzlepiece.fill", "Puzzle Piece"),
        ("crown.fill", "Crown"),
        ("flag.fill", "Flag"),
        ("bell.fill", "Bell"),
        ("megaphone.fill", "Megaphone"),

        // Row 8 — Creative / Music / Art
        ("paintbrush.fill", "Paintbrush"),
        ("pencil.and.ruler.fill", "Pencil and Ruler"),
        ("paintpalette.fill", "Paint Palette"),
        ("theatermasks.fill", "Theatre Masks"),
        ("music.note", "Music Note"),
        ("guitars.fill", "Guitars"),
        ("pianokeys", "Piano Keys"),
        ("headphones", "Headphones"),
        ("film", "Film"),
        ("camera.fill", "Camera"),

        // Row 9 — Sport / Movement
        ("figure.run", "Running"),
        ("figure.hiking", "Hiking"),
        ("bicycle", "Bicycle"),
        ("tennisball.fill", "Tennis Ball"),
        ("football.fill", "Football"),
        ("basketball.fill", "Basketball"),
        ("soccerball", "Football (Soccer)"),
        ("trophy.fill", "Trophy"),
        ("medal.fill", "Medal"),
        ("dumbbell.fill", "Dumbbell"),

        // Row 10 — Transport / Science / Learning
        ("airplane", "Aeroplane"),
        ("car.fill", "Car"),
        ("sailboat.fill", "Sailboat"),
        ("binoculars.fill", "Binoculars"),
        ("lightbulb.fill", "Light Bulb"),
        ("graduationcap.fill", "Graduation Cap"),
        ("book.fill", "Book"),
        ("scroll.fill", "Scroll"),
        ("stethoscope", "Stethoscope"),
        ("wand.and.stars", "Wand and Stars"),
    ]

    private let columns = Array(repeating: GridItem(.fixed(32), spacing: 4), count: 10)

    /// The effective icon name — nil means default.
    private var effectiveIcon: String {
        selectedIcon ?? Self.defaultIcon
    }

    var body: some View {
        LazyVGrid(columns: columns, spacing: 4) {
            ForEach(Self.palette, id: \.name) { icon in
                Button {
                    // Selecting the default icon stores nil (reset).
                    // Selecting anything else stores the name.
                    if icon.name == Self.defaultIcon {
                        onSelect(nil)
                    } else {
                        onSelect(icon.name)
                    }
                } label: {
                    Image(systemName: icon.name)
                        .frame(width: 32, height: 32)
                        .background(
                            effectiveIcon == icon.name
                                ? RoundedRectangle(cornerRadius: 6)
                                    .fill(Color.accentColor.opacity(0.2))
                                : nil
                        )
                        .overlay(
                            effectiveIcon == icon.name
                                ? RoundedRectangle(cornerRadius: 6)
                                    .strokeBorder(Color.accentColor, lineWidth: 1.5)
                                : nil
                        )
                }
                .buttonStyle(.plain)
                .accessibilityLabel(icon.label)
                .help(icon.label)
            }
        }
        .padding(12)
    }
}
