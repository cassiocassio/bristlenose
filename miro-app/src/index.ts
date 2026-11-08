// The app URL. Miro loads this page, unseen, whenever a board with the app installed opens; all it
// does is open the panel when the researcher clicks Bristlenose in the toolbar.

declare const miro: {
  board: { ui: { on(event: "icon:click", handler: () => void): void; openPanel(o: { url: string }): Promise<unknown> } };
};

miro.board.ui.on("icon:click", () => {
  void miro.board.ui.openPanel({ url: "app.html" });
});
