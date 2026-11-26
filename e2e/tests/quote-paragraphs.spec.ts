/**
 * A quote's own paragraphs, in a real browser against a real server
 * (docs/design-quote-editing.md §12a): Shift-Return while editing starts a
 * paragraph, Return saves it, and it is still there after a reload. The unit
 * tests drive the caret in jsdom, which lays nothing out and places a caret
 * as no browser does; these are the paths WebKit (the Mac app's engine) has
 * to prove (review 21 Nov 2026, finding 25; review 25 Nov, finding 28).
 *
 * This spec WRITES to the fixture's database, so each test puts its quote back
 * as it found it, and it refuses to run against a server that is not the
 * smoke fixture.
 */
import { test, expect, Page, Locator } from '@playwright/test';

test.describe.configure({ mode: 'serial' });

function authToken(): string {
  return process.env._BRISTLENOSE_AUTH_TOKEN ?? 'test-token';
}
const headers = { Authorization: `Bearer ${authToken()}` };

interface ApiQuote {
  dom_id: string;
  edited_text: string | null;
  researcher_breaks: number[] | null;
}

async function waitForPageReady(page: Page): Promise<void> {
  await page.waitForLoadState('load');
  await page.waitForFunction(() => document.querySelectorAll('.quote-text').length > 0, undefined, {
    timeout: 10_000,
  });
}

async function serverQuote(page: Page, baseURL: string, domId: string): Promise<ApiQuote | undefined> {
  const res = await page.request.get(`${baseURL}/api/projects/1/quotes`, { headers });
  const data = await res.json();
  const all = [...data.sections, ...data.themes].flatMap((g: { quotes: ApiQuote[] }) => g.quotes);
  return all.find((x) => x.dom_id === domId);
}

/** Open the smoke fixture's quotes and pin an unedited one-paragraph quote of six words or more. */
async function pickQuote(page: Page, baseURL: string): Promise<{ domId: string; card: Locator; text: Locator }> {
  const info = await page.request.get(`${baseURL}/api/projects/1/info`, { headers });
  expect(info.ok()).toBe(true);
  expect((await info.json()).project_name).toBe('Smoke Test');
  await page.goto('/report/quotes/');
  await waitForPageReady(page);
  const domId = await page.evaluate(() => {
    const cards = Array.from(document.querySelectorAll('blockquote.quote-card'));
    const ok = cards.find((c) => {
      const t = c.querySelector('.quote-text');
      return t && t.querySelectorAll('.bn-block').length <= 1 && (t.textContent ?? '').split(/\s+/).length >= 8;
    });
    return ok?.id ?? null;
  });
  expect(domId).toBeTruthy();
  const q = await serverQuote(page, baseURL, domId!);
  expect(q?.edited_text ?? null).toBeNull();
  expect(q?.researcher_breaks ?? null).toBeNull();
  // Pinned by id: a picker by shape stops matching once the quote has two paragraphs.
  const card = page.locator(`blockquote[id="${domId}"]`);
  return { domId: domId!, card, text: card.locator('.quote-text') };
}

/** Put the caret after the run's `n`th word, in the given paragraph (a break there is stored as `n - 1`). */
async function caretAfterWord(page: Page, domId: string, block: number, n: number): Promise<void> {
  await page.evaluate(
    ([id, b, k]) => {
      const run = document.querySelectorAll(`blockquote[id="${id}"] .quote-text .bn-block`)[b as number]
        .querySelector('.crop-editable')!;
      const node = run.firstChild!;
      const t = node.textContent ?? '';
      let at = 0;
      for (let i = 0; i < (k as number); i++) at = t.indexOf(' ', at + 1);
      const r = document.createRange();
      r.setStart(node, at + 1);
      r.collapse(true);
      getSelection()!.removeAllRanges();
      getSelection()!.addRange(r);
    },
    [domId, block, n],
  );
}

async function putBack(page: Page, baseURL: string, domId: string): Promise<void> {
  const edits = await page.request.patch(`${baseURL}/api/projects/1/edits`, { headers, data: { [domId]: null } });
  const breaks = await page.request.patch(`${baseURL}/api/projects/1/quote-breaks`, {
    headers,
    data: { [domId]: null },
  });
  expect(edits.ok() && breaks.ok()).toBe(true);
}

test('Shift-Return starts a paragraph that survives a reload, and writes no word edit', async ({ page, baseURL }) => {
  const errors: string[] = [];
  page.on('pageerror', (e) => errors.push(e.message));
  const { domId, card, text } = await pickQuote(page, baseURL!);
  try {
    await text.click();
    await expect(card).toHaveClass(/editing/);
    await caretAfterWord(page, domId, 0, 3);
    await page.keyboard.press('Shift+Enter');
    await expect(text.locator('.bn-block')).toHaveCount(2);
    await page.keyboard.press('Enter');
    await expect(card).not.toHaveClass(/editing/);
    // Return leaves the researcher on the card (finding 8).
    expect(await page.evaluate(() => document.activeElement?.id)).toBe(domId);

    await expect.poll(async () => (await serverQuote(page, baseURL!, domId))?.researcher_breaks).toEqual([2]);
    // Paragraphs alone are no edit of the words, so they do not pin the quote (finding 6).
    expect((await serverQuote(page, baseURL!, domId))?.edited_text ?? null).toBeNull();

    await page.reload();
    await waitForPageReady(page);
    await expect(page.locator(`blockquote[id="${domId}"] .quote-text .bn-block`)).toHaveCount(2);
    expect(errors).toEqual([]);
  } finally {
    await putBack(page, baseURL!, domId);
  }
});

test('a paragraph emptied and retyped keeps its words in that paragraph', async ({ page, baseURL }) => {
  // Finding 28: the engines remove a run once all its text is deleted, and the
  // caret must stay in that paragraph, or the words are typed into the next.
  const errors: string[] = [];
  page.on('pageerror', (e) => errors.push(e.message));
  const { domId, card, text } = await pickQuote(page, baseURL!);
  const original = ((await text.textContent()) ?? '').replace(/[“”]/g, '').trim().split(/\s+/);
  try {
    await text.click();
    await expect(card).toHaveClass(/editing/);
    await caretAfterWord(page, domId, 0, 3);
    await page.keyboard.press('Shift+Enter');
    await expect(text.locator('.bn-block')).toHaveCount(2);
    await caretAfterWord(page, domId, 1, 1);
    await page.keyboard.press('ControlOrMeta+a');
    await page.keyboard.press('Backspace');
    await page.keyboard.type('new words');
    await page.keyboard.press('Enter');
    await expect(card).not.toHaveClass(/editing/);

    const want = [...original.slice(0, 3), 'new', 'words'].join(' ');
    await expect.poll(async () => (await serverQuote(page, baseURL!, domId))?.edited_text).toBe(want);
    await expect.poll(async () => (await serverQuote(page, baseURL!, domId))?.researcher_breaks).toEqual([2]);
    expect(errors).toEqual([]);
  } finally {
    await putBack(page, baseURL!, domId);
  }
});

/** Select from paragraph `a`'s `ao`th word end to paragraph `b`'s `bo`th word end (0: its start). */
async function selectAcross(page: Page, domId: string, a: number, ao: number, b: number, bo: number): Promise<void> {
  await page.evaluate(
    ([id, pa, wa, pb, wb]) => {
      const run = (i: number) =>
        document.querySelectorAll(`blockquote[id="${id}"] .quote-text .bn-block`)[i].querySelector('.crop-editable')!
          .firstChild!;
      const at = (node: Node, k: number) => {
        const t = node.textContent ?? '';
        let x = 0;
        for (let i = 0; i < k; i++) x = t.indexOf(' ', x + 1);
        return k === 0 ? 0 : x < 0 ? t.length : x;
      };
      const r = document.createRange();
      const x = run(pa as number);
      const y = run(pb as number);
      r.setStart(x, at(x, wa as number));
      r.setEnd(y, at(y, wb as number));
      getSelection()!.removeAllRanges();
      getSelection()!.addRange(r);
    },
    [domId, a, ao, b, bo],
  );
}

test('Delete, typing and cut over a selection across a paragraph break act on it (26 Nov)', async ({ page, baseURL }) => {
  // These used to be refused: nothing happened, and a cut left the words in
  // place and on the clipboard. Now they act on the selected words and join
  // the paragraphs, and the quote marks stay.
  const errors: string[] = [];
  page.on('pageerror', (e) => errors.push(e.message));
  const { domId, card, text } = await pickQuote(page, baseURL!);
  const original = ((await text.textContent()) ?? '').replace(/[“”]/g, '').trim().split(/\s+/);
  const twoParagraphs = async () => {
    await text.click();
    await expect(card).toHaveClass(/editing/);
    await caretAfterWord(page, domId, 0, 3);
    await page.keyboard.press('Shift+Enter');
    await expect(text.locator('.bn-block')).toHaveCount(2);
  };
  const marks = () => text.locator('.bn-mark');
  try {
    // Backspace over words 3 to 5 (across the break): words 3, 4 and 5 go, one paragraph is left.
    await twoParagraphs();
    await selectAcross(page, domId, 0, 2, 1, 2);
    await page.keyboard.press('Backspace');
    await expect(text.locator('.bn-block')).toHaveCount(1);
    await expect(marks()).toHaveCount(2);
    // Typing over a selection that runs into the closing quote mark replaces the words to the end.
    await page.evaluate((id) => {
      const block = document.querySelector(`blockquote[id="${id}"] .quote-text .bn-block`)!;
      const run = block.querySelector('.crop-editable')!.firstChild!;
      const r = document.createRange();
      r.setStart(run, (run.textContent ?? '').indexOf(' ') + 1);
      r.setEnd(block, block.childNodes.length);
      getSelection()!.removeAllRanges();
      getSelection()!.addRange(r);
    }, domId);
    await page.keyboard.type('end');
    await expect(marks()).toHaveCount(2);
    await page.keyboard.press('Enter');
    const want = [original[0], 'end'].join(' ');
    await expect.poll(async () => (await serverQuote(page, baseURL!, domId))?.edited_text).toBe(want);
    await putBack(page, baseURL!, domId);

    // Cut across the break: the words leave the quote and are what the clipboard gets.
    await page.reload();
    await waitForPageReady(page);
    await twoParagraphs();
    await selectAcross(page, domId, 0, 2, 1, 1);
    // A script cannot run the native ⌘X (it needs a user gesture), so the cut
    // event the engine would send is sent here, with its own clipboard data.
    const cut = await page.evaluate((id) => {
      const data = new DataTransfer();
      const e = new ClipboardEvent('cut', { clipboardData: data, bubbles: true, cancelable: true });
      const taken = !document.querySelector(`blockquote[id="${id}"] .quote-text`)!.dispatchEvent(e);
      return { taken, text: data.getData('text/plain') };
    }, domId);
    expect(cut).toEqual({ taken: true, text: `${original[2]}\n${original[3]}` });
    await expect(text.locator('.bn-block')).toHaveCount(1);
    await page.keyboard.press('Enter');
    const left = [original[0], original[1], ...original.slice(4)].join(' ');
    await expect.poll(async () => (await serverQuote(page, baseURL!, domId))?.edited_text).toBe(left);
    expect(errors).toEqual([]);
  } finally {
    await putBack(page, baseURL!, domId);
  }
});
