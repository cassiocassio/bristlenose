# Icon Composer Layers — Bristlenose App Icon

These PNG layers are prepared for Apple's **Icon Composer** tool to create a
Liquid Glass `.icon` file for macOS 26 Tahoe and later.

## Layer files

| File | Purpose | Notes |
|------|---------|-------|
| `background.png` | Background fill | Blue-grey gradient, 1024×1024. Icon Composer can replace this with a System preset or custom fill |
| `foreground-default.png` | Fish artwork (light/default) | Transparent background, 1024×1024. Used for Default and Clear Light appearances |
| `foreground-dark.png` | Fish artwork (dark) | Transparent background, 1024×1024. Used for Dark and Clear Dark appearances |
| `foreground-mono.png` | White silhouette | Transparent background, 1024×1024. Used for Tinted (mono) appearances |

## How to assemble in Icon Composer

1. Open **Icon Composer** (Xcode → Open Developer Tool → Icon Composer, or download from [developer.apple.com/icon-composer](https://developer.apple.com/icon-composer/))
2. Select the canvas in the sidebar → Inspector → set background:
   - Either drag `background.png` as the background layer
   - Or use a **System Light** / **System Dark** preset (recommended for cleaner glass effect)
3. Drag `foreground-default.png` onto the canvas as the foreground layer
4. Adjust properties in the Inspector:
   - **Specular highlights**: subtle glow works well for the fish
   - **Translucency**: keep foreground mostly opaque (the fish should be clearly visible)
   - **Blur**: no blur on foreground; let the background blur come from the glass material
5. Switch to **Dark** appearance in the preview controls:
   - Swap the foreground to `foreground-dark.png`
6. Switch to **Mono** appearance:
   - Swap the foreground to `foreground-mono.png`
7. Preview all 6 appearances: Default, Dark, Clear Light, Clear Dark, Tinted Light, Tinted Dark
8. **Save** as `AppIcon.icon`
9. Drag the `.icon` file into the Xcode project navigator

## Integration with Xcode

After creating `AppIcon.icon`:

- **macOS 26 Tahoe+**: The system uses the `.icon` file directly with Liquid Glass rendering
- **macOS 15 Sequoia and earlier**: Xcode auto-generates flat PNGs from the `.icon` file at build time
- The flat PNGs in the parent `AppIcon.appiconset/` directory serve as fallback for builds without Icon Composer support

## Regenerating flat PNGs

If you update the source artwork:

```bash
python3 scripts/generate-app-icons.py
```

This reads from `bristlenose/theme/images/bristlenose.png` and `bristlenose-dark.png`.

## References

- [WWDC25: Create icons with Icon Composer](https://developer.apple.com/videos/play/wwdc2025/361/)
- [WWDC25: Say hello to the new look of app icons](https://developer.apple.com/videos/play/wwdc2025/220/)
- [Creating your app icon using Icon Composer](https://developer.apple.com/documentation/Xcode/creating-your-app-icon-using-icon-composer)
- [Apple Design Resources (templates)](https://developer.apple.com/design/resources/)
