H = """/* palette-{key} — {name}, {flavours}.
   {source}
   MIT licence. Colours the brand names are used verbatim; every other token is
   a mix of those, following the relationships in palette-default.css.
{adjust}
   Activate: data-color-theme="{key}" on <html>; BRISTLENOSE_PALETTE={key} or
   --palette {key}. Every palette comes in light and dark
   (tests/test_color_contract.py). */
"""

PALETTES = {
    "catppuccin": (
        H.format(key="catppuccin", name="Catppuccin", flavours="Latte (light) and Mocha (dark)",
                 source="Source: https://github.com/catppuccin/palette (catppuccin.com/palette).",
                 adjust="{adjust}"),
        dict(bg="#eff1f5", text="#4c4f69", muted="#6c6f85", border="#ccd0da", border_hover="#acb0be",
             accent="#8839ef", positive="#40a02b", negative="#d20f39", warning="#df8e1d",
             inspector="#e6e9ef", shadow="#4c4f69"),
        dict(bg="#1e1e2e", text="#cdd6f4", muted="#a6adc8", border="#313244", border_hover="#585b70",
             accent="#cba6f7", positive="#a6e3a1", negative="#f38ba8", warning="#f9e2af",
             inspector="#181825"),
    ),
    "rose-pine": (
        H.format(key="rose-pine", name="Rosé Pine", flavours="Dawn (light) and Main (dark)",
                 source="Source: https://rosepinetheme.com/palette. Rosé Pine has no green: success is pine/foam.",
                 adjust="{adjust}"),
        dict(bg="#faf4ed", text="#575279", muted="#797593", border="#dfdad9", border_hover="#cecacd",
             accent="#907aa9", positive="#286983", negative="#b4637a", warning="#ea9d34",
             inspector="#f2e9e1", sheet="#fffaf3", shadow="#575279"),
        dict(bg="#191724", text="#e0def4", muted="#908caa", border="#403d52", border_hover="#524f67",
             accent="#c4a7e7", positive="#9ccfd8", negative="#eb6f92", warning="#f6c177",
             inspector="#1f1d2e"),
    ),
    "solarized": (
        H.format(key="solarized", name="Solarized", flavours="light and dark",
                 source="Source: https://ethanschoonover.com/solarized/. The accents are the same in both appearances.",
                 adjust="{adjust}"),
        dict(bg="#fdf6e3", text="#073642", muted="#657b83", border="#eee8d5", border_hover="#93a1a1",
             accent="#268bd2", positive="#859900", negative="#dc322f", warning="#b58900",
             shadow="#002b36"),
        dict(bg="#002b36", text="#93a1a1", muted="#839496", border="#073642", border_hover="#586e75",
             accent="#268bd2", positive="#859900", negative="#dc322f", warning="#b58900"),
    ),
    "gruvbox": (
        H.format(key="gruvbox", name="Gruvbox", flavours="light and dark, medium contrast",
                 source="Source: https://github.com/morhetz/gruvbox. Light uses the faded accents, dark the bright ones.",
                 adjust="{adjust}"),
        dict(bg="#fbf1c7", text="#3c3836", muted="#7c6f64", border="#ebdbb2", border_hover="#bdae93",
             accent="#076678", positive="#79740e", negative="#9d0006", warning="#b57614",
             inspector="#f2e5bc", shadow="#3c3836"),
        dict(bg="#282828", text="#ebdbb2", muted="#a89984", border="#3c3836", border_hover="#665c54",
             accent="#83a598", positive="#b8bb26", negative="#fb4934", warning="#fabd2f",
             inspector="#32302f"),
    ),
}
