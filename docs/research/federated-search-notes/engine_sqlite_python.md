# Engine: "sufficiently fuzzy" full-text search on Python + SQLite

_Researched 27 Sep 2026. Two kinds of evidence below, kept distinct:_
- _**[web]** — a cited external source._
- _**[measured]** — run on the maintainer's Mac (arm64, macOS 27) on 27 Sep 2026 against the repo's own interpreters (`.venv`, `.venv-sidecar`, Homebrew 3.12/3.14, Xcode's `/usr/bin/python3`), and a scratch venv holding `tantivy 0.26.2`, `sqlite-utils 4.2.1` and `rapidfuzz`. The scripts are reproducible from the descriptions given. Timings come from a single warm run on an M-series Mac, so read them as orders of magnitude, not benchmarks._

---

## 1. SQLite FTS5 capabilities, and which SQLite each Bristlenose channel actually gets

### Takeaway
FTS5 has everything a "fuzzy enough" engine needs: `unicode61` word index with diacritic folding, a `trigram` tokenizer for substring and CJK, prefix indexes, per-column weighted `bm25()`, `snippet()`/`highlight()`, and external-content tables kept in sync by triggers. Every Bristlenose Mac interpreter measured has it compiled in, at SQLite 3.53.3. **The binding constraint is Linux.** Ubuntu 22.04 ships 3.37.2 and the snap (core24) gets 3.45.1. Features newer than 3.45 (`locale=1`, `contentless_unindexed`, the tokenizer v2 API) cannot be assumed, and the code must probe for features at runtime.

### Cited findings

**Tokenizers**
- `unicode61` takes `remove_diacritics` 0, 1 or 2 (default 1). Mode 2 "correctly removes diacritics from all Latin characters". Mode 1 has a known defect with codepoints carrying several diacritics (e.g. U+1ED9). Other options: `categories` (default `"L* N* Co"`), `tokenchars` and `separators`. — [SQLite FTS5 docs](https://sqlite.org/fts5.html)
- `porter` is a wrapper tokenizer (English Porter stemming) that wraps `unicode61` by default, e.g. `tokenize = 'porter unicode61 remove_diacritics 1'`. — [SQLite FTS5 docs](https://sqlite.org/fts5.html)
- The built-in tokenizers are `unicode61`, `ascii`, `porter` and `trigram`. FTS5 has no ICU or Snowball tokenizer. — [SQLite FTS5 docs](https://sqlite.org/fts5.html); [APSW text-search docs](https://rogerbinns.github.io/apsw/textsearch.html) ("SQLite's four built-ins")
- `trigram` shipped in **SQLite 3.34.0 (Dec 2020)**. Its `remove_diacritics` option needs **3.45.0**. — [web search summary citing SQLite forum](https://sqlite.org/forum/forumpost/fa267e228dba5d892cf34efeb112600cd6090a6d5846d12f857d2fd9d2840767); [tagalot PR requiring 3.45+ for trigram remove_diacritics](https://github.com/torstees/tagalot/pull/148). _(One fetched summary of the FTS5 page wrongly said "3.9.0". 3.9.0 is when FTS5 itself arrived, not trigram.)_
- Trigram options: `case_sensitive` 0 (default) or 1; `remove_diacritics` 0 (default) or 1, the latter only valid with `case_sensitive=0`. "Unless the remove_diacritics option is set, FTS5 tables that use the trigram tokenizer also support indexed GLOB and LIKE pattern matching." Substrings shorter than 3 characters never match in a MATCH query. A LIKE/GLOB pattern with no run of 3+ literal characters falls back to a linear scan. — [SQLite FTS5 docs](https://sqlite.org/fts5.html)

**Index structure and upkeep**
- Prefix indexes: `prefix='2 3'` (or repeated `prefix=` options). They speed up `foo*` queries at a storage cost. — [SQLite FTS5 docs](https://sqlite.org/fts5.html)
- Ranking: `ORDER BY bm25(ft, 10.0, 5.0)` gives per-column weights, leftmost column first. Weights can be made the default via `INSERT INTO ft(ft, rank) VALUES('rank', 'bm25(10.0, 5.0)')`, after which `ORDER BY rank` uses them. — [SQLite FTS5 docs](https://sqlite.org/fts5.html)
- `highlight(ft, col, '<b>', '</b>')` and `snippet(ft, col|-1, open, close, ellipsis, max_tokens 1..64)`. — [SQLite FTS5 docs](https://sqlite.org/fts5.html)
- Storage modes. An external-content table (`content='t', content_rowid='id'`) holds only the index and reads columns back from the base table. A contentless table (`content=''`) cannot return column values. A contentless-delete table (`content='', contentless_delete=1`, **3.43.0+**) supports DELETE/REPLACE, but an UPDATE must supply every column. `contentless_unindexed=1` is **3.47.0+**. — [SQLite FTS5 docs](https://sqlite.org/fts5.html); [SQLite release history](https://sqlite.org/changes.html)
- Other version-gated features: `secure-delete` (3.42.0), `insttoken` (3.41.0), `tokendata` (3.45.0), the FTS5 integrity check in `PRAGMA integrity_check` (3.44.0), and `locale=1` with the `fts5_tokenizer_v2` API and `fts5_locale()` (**3.47.0**, 21 Oct 2024). The newest release is **3.53.4 (24 Jul 2026)**. — [SQLite release history](https://sqlite.org/changes.html)
- Official sync triggers for external content. This is verbatim; note that the delete takes the *old* values:
  ```sql
  CREATE TRIGGER t1_ai AFTER INSERT ON t1 BEGIN
    INSERT INTO fts_idx(rowid, b, c) VALUES (new.a, new.b, new.c);
  END;
  CREATE TRIGGER t1_ad AFTER DELETE ON t1 BEGIN
    INSERT INTO fts_idx(fts_idx, rowid, b, c) VALUES('delete', old.a, old.b, old.c);
  END;
  CREATE TRIGGER t1_au AFTER UPDATE ON t1 BEGIN
    INSERT INTO fts_idx(fts_idx, rowid, b, c) VALUES('delete', old.a, old.b, old.c);
    INSERT INTO fts_idx(rowid, b, c) VALUES (new.a, new.b, new.c);
  END;
  ```
  — [SQLite FTS5 docs](https://sqlite.org/fts5.html)
- Maintenance commands. `'rebuild'` (external-content tables only, not contentless). `'optimize'` merges everything into one b-tree. `'merge', N` does incremental work (negative N merges aggressively). `automerge` defaults to 4, `crisismerge` to 16, `usermerge` to 4. — [SQLite FTS5 docs](https://sqlite.org/fts5.html)

**Which SQLite each channel gets**
- **[measured]** `.venv` and `.venv-sidecar` (CPython 3.12.13), Homebrew `python3.12` and Homebrew `python3.14` all report **SQLite 3.53.3**. Their compile options include `ENABLE_FTS5`, `ENABLE_FTS3`, `ENABLE_RTREE` and `ENABLE_MATH_FUNCTIONS`. `trigram remove_diacritics 1` and `contentless_delete=1` both create successfully, and `enable_load_extension` is present. No `ENABLE_ICU` in any of them. Xcode's `/usr/bin/python3` (3.9.6) has SQLite 3.54.0 **with `OMIT_LOAD_EXTENSION`**, so it has no `enable_load_extension`.
- **[measured]** The shipped desktop sidecar bundles `_internal/libsqlite3.dylib`, whose embedded source id is dated `2026-06-26 20:14:12`, matching the 3.53.x line that `.venv-sidecar` reports.
- python.org macOS/Windows installers for 3.12 moved to SQLite 3.45.1 and then 3.45.3. — [cpython#115009](https://github.com/python/cpython/issues/115009)
- Ubuntu 22.04 ships sqlite3 **3.37.2**, 24.04 ships **3.45.1** and 26.04 ships 3.46.x. — [LinuxCapable summary](https://linuxcapable.com/how-to-install-sqlite-on-ubuntu-linux/); [packages.ubuntu.com noble](https://packages.ubuntu.com/noble/sqlite3)
- **[measured, repo]** The snap is `base: core24` and stages the distro `libpython3.12-stdlib`, so it links Ubuntu 24.04's libsqlite3 (3.45.1). `pyproject.toml` still says `requires-python = ">=3.10"`.

### Inferences
- **Feature floor.** Pin design to **3.45** (snap, Ubuntu 24.04, python.org 3.12). That covers trigram with `remove_diacritics`, contentless-delete, secure-delete and `tokendata`. It excludes `locale=1` and the tokenizer v2 API (3.47), so a per-row language-aware tokenizer cannot be the baseline.
- **Linux degrade path.** A pip user on Ubuntu 22.04 (3.37.2) gets trigram without diacritic folding and no contentless-delete. The engine should probe at startup (`sqlite3.sqlite_version_info`, or try-create a throwaway virtual table) and degrade to a `LIKE` scan rather than fail.
- **Table choice.** External-content tables with the triggers above are the right default. Bristlenose already keeps the canonical text in ordinary tables, the "edits must be searchable immediately" requirement is met transactionally by the triggers, and `snippet()` works because the content is readable.
- **Probe the feature, not the version.** The `ENABLE_FTS5` compile flag is present on every measured build, but distro builds can differ, so probing beats version-sniffing.

### Gaps
- The exact SQLite in the *last* python.org 3.12 macOS installer (3.12 went security-only, and later releases have no binary installers) was not confirmed.
- Whether that installer's `sqlite3` supports `enable_load_extension` is unconfirmed. [Simon Willison's TIL](https://til.simonwillison.net/sqlite/sqlite-extensions-python-macos) confirms only that Homebrew Python does.
- The SQLite version in Fedora 43's `python3.14` (the Copr channel) was not checked.
- manylinux wheels don't bundle SQLite (CPython's `_sqlite3` links the host library), so pip-on-Linux is whatever the distro ships. That is inferred from how CPython builds `_sqlite3`, not verified per distro.

---

## 2. Fuzziness strategies layered on FTS5

### Takeaway
"Sufficiently fuzzy" on stock SQLite plus Python comes from four layers:
- **prefix queries** (`term*`, optionally backed by `prefix='2 3'`) for search-as-you-type;
- **diacritic and case folding** (`remove_diacritics 2`);
- a **trigram** table for substring and mid-word matches;
- a Python-side **"did you mean"** that runs `rapidfuzz` over the index vocabulary (`fts5vocab`).

`spellfix1`/`editdist3` are not built into any Python build measured, and would need a custom-compiled loadable extension. Stemming is English-only in FTS5. Multilingual stemming means either pre-stemming in Python (Snowball) into a shadow column, or a different engine.

### Cited findings
- **[measured]** `load_extension('spellfix')` fails on Homebrew Python 3.12 (no such dylib), and `editdist3()` does not exist as a built-in function. spellfix1 ships only as source in SQLite's `ext/misc`, so using it means compiling a `.dylib`/`.so` per platform and loading it with `enable_load_extension(True)`.
- `sqlean.py` (a drop-in `sqlite3` replacement bundling a `fuzzy` extension, among others) was **archived on 4 Feb 2026: "The project is no longer maintained."** Its wheels cover Linux and macOS only, no Windows. — [sqlean.py repo](https://github.com/nalgeon/sqlean.py). **[measured]** Its last PyPI release is 3.50.4.5 (25 Oct 2025).
- APSW (latest 3.53.4.0, 26 Jul 2026 **[measured, PyPI]**) lets FTS5 tokenizers and auxiliary functions be written in Python. It ships `UnicodeWordsTokenizer`, `NGramTokenizer` (grapheme-cluster n-grams), `SimplifyTokenizer` (case and diacritics), `RegexTokenizer`, `SynonymTokenizer` and `StopWordsTokenizer`, plus `query_suggest("querry")`, `closest_tokens("teh", n, cutoff)` (difflib-based) and `token_doc_frequency()`. The docs warn that Python tokenizers make initial indexing slow. — [APSW text search docs](https://rogerbinns.github.io/apsw/textsearch.html)
- The stdlib `sqlite3` module cannot register FTS5 tokenizers. It has no binding for `fts5_api` (general knowledge; APSW exists largely to fill that gap, as its docs show). — [APSW text search docs](https://rogerbinns.github.io/apsw/textsearch.html)
- **[measured]** `rapidfuzz` 3.14.6 (30 Aug 2026) ships wheels for macOS arm64/x86_64 and requires Python ≥3.11. Current is ≥3.11, so a **3.10 floor would pin an older rapidfuzz**. This matters only until the planned 3.12 floor lands.

**"Did you mean" via vocabulary** (standard pattern; `fts5vocab` is documented on [sqlite.org/fts5.html](https://sqlite.org/fts5.html)):
```sql
CREATE VIRTUAL TABLE seg_vocab USING fts5vocab('seg_fts', 'row');  -- term, doc, cnt
```
```python
from rapidfuzz import process, fuzz, distance
vocab = dict(conn.execute("SELECT term, doc FROM seg_vocab WHERE doc >= 2"))  # ~tens of k terms
def did_you_mean(tok):
    hits = process.extract(tok, vocab.keys(), scorer=distance.Levenshtein.normalized_similarity,
                           limit=5, score_cutoff=0.75)
    return max(hits, key=lambda h: (h[1], vocab[h[0]]))[0] if hits else None
```
Run it only when the MATCH returns zero or very few hits. Cache the vocabulary per project and invalidate it on write.

**Stemming**
- **[measured]** tantivy-py's `Filter.stemmer()` accepted `"german"` and `"russian"` (`работающих` → `работа`) and rejected `"japanese"` ("Unsupported language"). The Snowball family has no CJK stemmers by nature.

### Inferences
- Plain prefix queries (`chec*`) on a plain `unicode61` index already answer in ~2.6 ms at 100k segments (§6). `prefix='2 3'` bought little query time (2.1 ms) and cost 4× the build time and 2.6× the index size. **Skip prefix indexes by default.**
- **Recommended query rewrite** for a user string `q`: tokenise it the way unicode61 would, quote each token (to neutralise FTS5 syntax: `"`, `*`, `-`, `AND`/`OR`/`NOT`, `:`), and append `*` to the last token only. sqlite-utils does the same kind of escaping. Search-as-you-type then looks like `"checkout" "flo"*`.
- Typo tolerance should stay **query-side** (vocabulary plus rapidfuzz), not index-side. It is cheap, needs no extension, works on every channel and every SQLite ≥3.9, and localises trivially because the vocabulary is whatever tokens are in the corpus, in any language.
- If multilingual stemming is wanted, pre-stem in Python with a pure-Python Snowball implementation into a hidden `text_stem` column, and query both columns. Weigh the cost first: a *project language* has to be chosen per segment, and Bristlenose already detects the transcript language. This is optional polish, not a baseline.

### Gaps
- No benchmark was run of rapidfuzz over a realistic vocabulary (~30–100k terms). Published rapidfuzz performance suggests single-digit milliseconds, but that is unmeasured here.
- `snowballstemmer`/`PyStemmer` versions and wheel status were not checked.

---

## 3. CJK (and other scripts where `unicode61` misbehaves)

### Takeaway
`unicode61` **does not segment CJK at all**. A whole run of Han/kana/Hangul becomes **one token**, so only a query equal to that entire run matches. Trigram fixes 3+ character CJK queries. **1–2 character queries** (very common in Chinese and Japanese) need one of three things:
- a `LIKE`/`instr` fallback scan, which is cheap at Bristlenose scale (~15 ms per 100k segments, measured);
- a bigram or unigram n-gram tokenizer, which needs APSW or a custom C extension;
- a different engine.

Beyond CJK, several **non-Latin folding gaps** matter for the 22 locales: Russian `ё`/`е`, Turkish `İ` under trigram, and German `ü`→`ue`.

### Cited findings
- **[measured]** The `fts5vocab` of a `unicode61` table holding `東京の地下鉄はとても便利です` and `我覺得這個設計很好用` contains exactly those two strings as terms. Each sentence is one token.
- **[measured]** Match results by tokenizer:

  | query → doc | `unicode61` | `trigram` | `trigram remove_diacritics 1` |
  |---|---|---|---|
  | `地下鉄` → Japanese sentence | 0 | **1** | **1** |
  | `東京` (2 chars) | 0 | 0 | 0 |
  | `東` (1 char) | 0 | 0 | 0 |
  | `設計` (2 chars, zh-Hant) | 0 | 0 | 0 |
  | `디자인` → `디자인이 정말 좋아요` (Korean particle attached) | 0 | **1** | **1** |
  | `cafe` → `Café` | **1** | 0 | **1** |
  | `ueberpruefung` → `Überprüfung` | 0 | 0 | 0 |
  | `елка` → `Ёлка` (Russian) | **0** | 0 | **0** |
  | `istanbul` → `İstanbul` (Turkish) | **1** | **0** | **1** |
  | `kun` → `kůň` (Czech) | **1** | 0 | **1** |

- **[measured]** `EXPLAIN QUERY PLAN` for `x LIKE '%地下%'` on a trigram table shows `INDEX 0:` (a full scan) and still returns the right row. The 2-character pattern cannot use trigrams.
- **[measured]** A full-table `LIKE '%xy%'` or `instr(text, 'xy') > 0` over **100,000 rows × 40 CJK chars** takes **~15 ms**, and a 1-character LIKE likewise ~15 ms (in memory, warm).
- `sqlite-better-trigram` (streetwriters, the Notesnook team) treats each CJK character as its own token, indexes words shorter than 3 chars, and treats spaces as word boundaries. It is built as a **loadable extension** (`.load better-trigram.so`, `tokenize='better_trigram'`) with a Make/Lemon/Tcl build, under the SQLite blessing licence, with 47 stars. — [sqlite-better-trigram](https://github.com/streetwriters/sqlite-better-trigram)
- Others have written up the "trigram + trick" approach for unigram/bigram CJK. — [tkys/sqlite-fts5-trigram-trick](https://github.com/tkys/sqlite-fts5-trigram-trick); [Zenn: CJK FTS5 trigram hybrid strategy](https://zenn.dev/kanseilink/articles/kanseilink-fts5-trigram-cjk-20260507?locale=en) (fetch returned 403, content not verified).
- APSW's `NGramTokenizer` works on grapheme clusters with configurable n, so a Python-defined 1–2-gram tokenizer is possible with APSW. — [APSW text search docs](https://rogerbinns.github.io/apsw/textsearch.html)
- **[measured]** tantivy-py 0.26.2's default tokenizer also fails CJK (`東京` → 0, `地下鉄` → 0). Its `Tokenizer.ngram(min_gram=1, max_gram=2)` produces `['東','東京','京','京の','の','の地','地','地下','下','下鉄','鉄']`, a usable CJK unigram+bigram index. No lindera/jieba morphological tokenizer is exposed in the Python bindings (only `raw`, `simple`, `whitespace`, `regex`, `ngram`, `facet`).
- No local Python has `ENABLE_ICU` **[measured]**, and FTS5 has no ICU tokenizer in any case. — [SQLite FTS5 docs](https://sqlite.org/fts5.html)

### Inferences
- **Recommended CJK design with stock SQLite.** Keep a single `trigram remove_diacritics 1` index as the substring index for every language. For queries whose longest CJK run is under 3 characters, route to `instr()` or `LIKE` over the base table. At ≤100k segments per project that scan is ~15–80 ms, well inside a search-as-you-type budget.
  - Trigram cannot rank or snippet 1–2 character matches. Do those with Python-side windowing, or with a trigram `highlight()` on a longer surrounding context.
  - The next step up, only if measured necessary, is a CJK bigram shadow column. Segment in Python (split CJK runs into overlapping bigrams plus unigrams, separated by spaces) and index that column with `unicode61`. It is pure stdlib, needs no extension, and the query applies the same transform.
- **Two indexes, not one.** `unicode61 remove_diacritics 2` serves as the *word* index (ranking, snippets, prefix, "did you mean") and trigram as the *substring/CJK* index.
- **Pre-fold text for non-Latin cases.** Unicode61's diacritic removal is Latin-only. Russian/Ukrainian `ё`→`е` needs an explicit fold, applied at index time (a folded shadow column, or folding before insert into a contentless-delete index) and again at query time. The Turkish dotted/dotless i (`İ`, `ı`) is case-mapping-sensitive. Apply `str.casefold()` plus a small replacement table in Python on both sides. German `ü`↔`ue` transliteration is a user expectation that no tokenizer meets and is probably out of scope.

### Gaps
- Real Japanese/Chinese transcript text (as opposed to random CJK codepoints) was not tested, so result quality for 1–2-character queries under a scan (false positives inside longer words) is unmeasured.
- Korean is agglutinative, so particles attach to nouns. Trigram handled `디자인이` for `디자인`, but a 2-syllable Korean noun query would hit the same <3-char problem. Not measured.

---

## 4. Python alternatives and complements

### Takeaway
- **rapidfuzz** is the right tool for short fields (people, tags, themes, headings: hundreds of rows). Score all of them in memory, with no index.
- **tantivy-py** is a credible full engine, with real fuzzy term queries, Snowball stemmers, n-gram tokenizers and snippets. But it is a second store to keep in sync with SQLite, holds a **single-writer lockfile**, and adds ~23 MB of native code.
- **Whoosh is dead.**
- **Semantic search** (sqlite-vec plus a small multilingual embedding model) is possible but **pre-v1** and needs extension loading. Keyword search is the baseline, and vectors are an optional later layer fused with RRF.

### Cited findings
- **[measured, PyPI]** tantivy **0.26.2** (17 Sep 2026) requires Python ≥3.10 and ships macOS universal2/x86_64 wheels.
- **[measured]** tantivy-py 0.26.2 behaviour:
  - `Query.fuzzy_term_query(schema, "text", "chekout", distance=1)` found both "checkout" docs, and `prefix=True` with "chekou" did too. `ix.parse_query("chekout", ["text"], fuzzy_fields={"text": (True, 1, False)})` works.
  - `SnippetGenerator` exists. Delete+add+`commit()`+`reload()` made an edited doc searchable immediately.
  - **A second `ix.writer()` raised `LockBusy`.** The installed package is **23 MB**. `Filter.ascii_fold()` exists, but the default tokenizer matched `café` and not `cafe`, so folding must be configured explicitly.
- Wheels exist for common platforms, but "if no binary wheel is present … Rust needs to be installed". — [tantivy on PyPI](https://pypi.org/project/tantivy/0.20.1/); [tantivy-py releases](https://github.com/quickwit-oss/tantivy-py/releases)
- **[measured, PyPI]** Whoosh's last release is **2.7.4, 4 Apr 2016**. The `Whoosh-Reloaded` fork's is 2.7.5, 2 Feb 2024. Both are effectively unmaintained.
- sqlite-vec: "pre-v1, so expect breaking changes". It offers brute-force and ANN, float/int8/bit vectors, and metadata/partition columns. In Python it loads via `sqlite_vec.load(conn)` after `enable_load_extension(True)`, and the README notes that macOS default Python may not load extensions. — [sqlite-vec repo](https://github.com/asg017/sqlite-vec). **[measured, PyPI]** The latest is **0.1.9 (31 Mar 2026)**, with macOS arm64 wheels.
- potion-multilingual-128M (model2vec) is a **static** embedding model distilled from BGE-M3. It covers 101 languages, has 256 dimensions and no input-length limit, and scores 47.31 mean on MTEB, "90.86% of the performance of LaBSE", while being "orders of magnitude faster". — [Hugging Face model card](https://huggingface.co/minishlab/potion-multilingual-128M); [model2vec results](https://github.com/MinishLab/model2vec/blob/main/results/README.md). **[measured, PyPI]** `model2vec` 0.9.0 (12 Aug 2026) and `fastembed` 0.8.1 (22 Sep 2026) are current.
- Hybrid ranking via RRF, from Simon Willison's SQL:
  `coalesce(1.0/(:rrf_k + fts.rank_number), 0) * :weight_fts + coalesce(1.0/(:rrf_k + vec.rank_number), 0) * :weight_vec`, with `row_number()` per list. The rationale: FTS scores and vector distances are "meaningless in comparison to each other". — [Simon Willison, Oct 2024](https://simonwillison.net/2024/Oct/4/hybrid-full-text-search-and-vector-search-with-sqlite/)

### Inferences
- **rapidfuzz for small entity sets.** At a few hundred names/tags/themes, `process.extract(q, choices, scorer=fuzz.WRatio)` (or `partial_ratio` for type-ahead) over an in-memory list takes well under a millisecond, handles typos and transpositions, and needs no index maintenance. Do it server-side so the CLI and MCP benefit too.
- **tantivy only as a pluggable backend.** It is worth considering only if FTS5 plus the Python layers measurably fall short, especially for CJK n-grams with fuzzy matching. Costs:
  - a second on-disk index per project, kept in sync outside SQLite transactions, which breaks the "edits searchable immediately, atomically" property unless each write path is dual-written;
  - a single-writer lock that constrains a multi-process sidecar;
  - 23 MB of native code to sign in the sandboxed bundle.
- **Semantic search: defer.**
  - Brute-force cosine over ~100k × 256-d float32 (~100 MB) is feasible in numpy, even without sqlite-vec.
  - A static model (model2vec) avoids a transformer runtime, so it is cheap to embed locally.
  - Bristlenose's users search for *words they remember* (quotes, names, tags), which is a keyword job. Semantic search mostly adds "find things about X", and the existing LLM-grounded chat lens already covers that job.
  - Cloud embeddings would be a per-project spend and an extra outbound call per edit.

### Gaps
- tantivy index size and query latency on the 100k-segment corpus were not measured. Only the 5-document functional probe was run.
- PyInstaller-specific packaging of tantivy (hidden imports, codesign under hardened runtime) was not tested.
- No multilingual retrieval benchmark specific to interview transcripts was found.

---

## 5. Real-world implementations

### Takeaway
The house pattern across the SQLite ecosystem is: `<table>_fts` external-content FTS5 plus AFTER INSERT/DELETE/UPDATE triggers, a join back to the base table, and `ORDER BY rank`. That is Datasette/sqlite-utils. Joplin shows that production apps layer **discrete ranking rules** on top of BM25 (title matches first, then weighted BM25 with recency) rather than trusting one score.

### Cited findings
- **[measured, source read]** `sqlite-utils` 4.2.1 `Table.enable_fts(create_triggers=True)` creates `{table}_ai`, `{table}_ad` and `{table}_au` triggers on `{table}_fts`. They are the same shape as the official triggers: 'delete' with old values, then insert the new ones. `search_sql()` builds:
  ```sql
  with original as (select rowid, <cols> from <table> [where ...])
  select <cols> from original join <table>_fts on original.rowid = <table>_fts.rowid
  where <table>_fts match :query order by <table>_fts.rank [limit/offset]
  ```
  For FTS4 it instead registers a Python `rank_bm25(matchinfo(...,'pcnalx'))`.
- Joplin's ranking: "search results with note title matches will appear above all results that only matched the note body, regardless of weight". The weight is BM25, where a term in more than half the notes has weight zero, boosted by "the inverse number of days since the note was updated". Ties are broken by to-do status, then age. — [Joplin search sorting spec](https://joplinapp.org/help/dev/spec/search_sorting)
- Hybrid FTS5 + sqlite-vec + RRF has become a common template, e.g. [liamca/sqlite-hybrid-search](https://github.com/liamca/sqlite-hybrid-search) and [cap-js/mcp-server PR #164](https://github.com/cap-js/mcp-server/pull/164). — also [Simon Willison](https://simonwillison.net/2024/Oct/4/hybrid-full-text-search-and-vector-search-with-sqlite/)

### Gaps
- Zotero, Calibre and Obsidian Omnisearch internals were not researched, for lack of tool budget. Obsidian Omnisearch uses MiniSearch (JS, in memory), which is not SQLite. That is general knowledge, not verified here.
- Joplin's FTS version and its CJK fallback were not stated on the fetched page.

---

## 6. Performance at Bristlenose scale

### Takeaway
At **100k segments / ~7M words**, the costs are:

| index | build | size | query |
|---|---|---|---|
| `unicode61` | ~3.5 s | ~0.5× the text | ~1 ms word, ~2.6 ms prefix |
| `trigram` | ~27 s | **~3.4×** the text | ~4–6 ms |

All are comfortably interactive. Trigram size is the one number to watch: roughly 200 MB per 60 MB of transcript text.

### Cited findings
- **[measured]** Corpus: 100,000 rows × 70 words drawn from a 30,000-word random-letter vocabulary. That is 7M tokens and 58.7 MB of base-table content, in a file-backed WAL database, with the index built by `'rebuild'` from an external-content table:

  | tokenizer | build | index `_data` size | exact-term top-50 by rank | prefix (`abc*`) / 3-char substring top-50 | `snippet()` top-20 |
  |---|---|---|---|---|---|
  | `unicode61 remove_diacritics 2` | 3.5 s | **28.6 MB** | 0.98 ms | 2.6 ms | 0.83 ms |
  | same + `prefix='2 3'` | 14.8 s | 74.5 MB | 1.15 ms | 2.1 ms | 0.67 ms |
  | `trigram remove_diacritics 1` | 26.6 s | **202.2 MB** | 5.9 ms | 4.3 ms | 5.1 ms |

  `_docsize` adds ~1 MB per index. Caveat: random-letter words are harder on the index than natural Zipfian text, so read these as upper-ish bounds for `unicode61` and roughly representative for trigram.
- FTS5 merges segments incrementally (`automerge` 4, `crisismerge` 16), so per-edit trigger cost stays small and `'optimize'` is optional housekeeping. — [SQLite FTS5 docs](https://sqlite.org/fts5.html)

### Inferences
- The initial index build belongs in the pipeline's render/import step, or lazily on first `serve`, with a one-off 30 s trigram build shown as progress. Per-edit trigger updates are sub-millisecond-scale inserts.
- Trigram's 3.4× blow-up argues for indexing **only searchable text columns** into trigram (segment text, quote text), not metadata, and for considering `detail=none` or `detail=column` on the trigram table. That shrinks it at the cost of phrase queries, which trigram barely needs.
- Under WAL, readers never block on the single writer. A search request running during a quote edit sees a consistent snapshot. General SQLite WAL semantics, not measured here.

### Gaps
- `detail=none|column` size savings were not measured.
- Concurrent write+search contention was not measured.
- Natural-language (Zipfian) corpus numbers are missing; running the benchmark on a real `trial-runs/` project DB would firm them up.

---

## 7. Cross-database search (one DB per project)

### Takeaway
FTS5 `MATCH` **works on ATTACHed databases**, and a `UNION ALL` across schemas works **[measured]**, but the default attach limit is **10**. More importantly, **bm25 scores are corpus-relative and not comparable across databases**. Fan out per project (parallel connections), take each project's top N, and merge by **rank position (RRF)** rather than raw score.

### Cited findings
- **[measured]** With `ATTACH 'b.db' AS b`:
  - `SELECT rowid, bm25(q) FROM b.q WHERE q MATCH 'checkout'`, `WHERE b.q.q MATCH ...` and the table-valued form `FROM b.q('checkout')` all work.
  - **Aliasing an FTS5 table breaks auxiliary functions**: `FROM b.q bq … bm25(bq)` errors with "no such column: bq".
  - A cross-schema union works when each arm is a subquery:
    ```sql
    SELECT * FROM (SELECT 'a' db, rowid, bm25(q) s FROM main.q WHERE main.q.q MATCH 'checkout')
    UNION ALL
    SELECT * FROM (SELECT 'b', rowid, bm25(q) FROM b.q WHERE b.q.q MATCH 'checkout')
    ORDER BY s LIMIT 4;
    ```
- **[measured]** `conn.getlimit(sqlite3.SQLITE_LIMIT_ATTACHED)` returns **10** on the `.venv` build. It can only be lowered at runtime. Raising it needs a compile-time `SQLITE_MAX_ATTACHED` (hard max 125, general SQLite knowledge; not re-verified this session).
- **[measured]** Score non-comparability, concretely. "checkout" appears in 2 of 2 docs in `a.db` and in 50 of 100 docs in `b.db`, and both give bm25 ≈ **−1e-6**, i.e. essentially zero. BM25's IDF collapses when a term is in ≥ half the documents, which Joplin also notes. The same match in a project where the term is rare would score orders of magnitude higher. — corroborated by [Joplin spec](https://joplinapp.org/help/dev/spec/search_sorting)

### Inferences
- **Fan out, don't ATTACH.** Run one read connection per project in a thread pool (sqlite3 releases the GIL during query execution). Ask each for its top K (e.g. 20) with a `row_number()` rank, and merge in Python with RRF (`1/(60 + rank)`, k=60 being the conventional constant). This avoids the attach limit, lets projects be searched as they open or lazily, and makes the merge scale-free.
- If a global "search everything" index is ever wanted, the alternative is a **single instance-level search DB**: a contentless-delete FTS5 table (3.43+) keyed by `(project_id, entity, id)`, fed by the per-project write paths. That gives one corpus and one IDF, so scores become comparable, at the cost of dual writes. It should be weighed against Bristlenose's per-project ownership model (the report is a file the researcher owns).

### Gaps
- Parallel fan-out latency across, say, 20 project DBs was not measured.

---

## 8. Ranking across heterogeneous entity types

### Takeaway
Don't try to put a person name, a tag and a transcript line on one numeric scale. Rank **within each entity type** (rapidfuzz score for short fields, bm25 for long text), then combine by **position**, via RRF or fixed per-type quotas/sections, with explicit tie-breaking rules in the Joplin style. That is the documented practice for fusing incomparable scorers.

### Cited findings
- RRF exists precisely because different scorers' outputs are "meaningless in comparison to each other". It combines by `row_number()` position. — [Simon Willison](https://simonwillison.net/2024/Oct/4/hybrid-full-text-search-and-vector-search-with-sqlite/)
- Joplin uses discrete priority tiers: title-match first, then weight, then secondary keys. — [Joplin search sorting spec](https://joplinapp.org/help/dev/spec/search_sorting)
- FTS5 per-column weights (`bm25(ft, 10.0, 5.0)`) let a single table rank a heading hit above a body hit. This is useful if several text fields of one entity (quote text, its edited text, its section heading) share an FTS row. — [SQLite FTS5 docs](https://sqlite.org/fts5.html)

### Inferences
Suggested engine shape, for the synthesiser:
1. **Short entities** (people, tags, themes, sections, codebook tags: hundreds of rows). Hold them in Python memory per project, scored with rapidfuzz (`WRatio`, plus a bonus for exact-prefix matches). Rebuild the list on write, which is cheap.
2. **Quotes** (thousands). FTS5 `unicode61 remove_diacritics 2` external-content table over `(text, edited_text, heading)` with weights like `bm25(q_fts, 1, 1.5, 3)`, plus a trigram table for substring and CJK.
3. **Transcript segments** (≤100k). The same pair of FTS5 tables, with `snippet()` for display.
4. **Merge.** Either present per-type groups ("People · Tags · Quotes · Transcript", each ranked internally), which is the usual command-palette UX, or build a single list by RRF across the per-type lists with type priors (multiply by a per-type weight).
   - Exact or whole-token matches in short entities should outrank fuzzy transcript hits. Implement that as a tier rule, not a score tweak.
5. **Query pipeline.**
   - Normalise the query: NFKC, casefold, the `ё`→`е` and Turkish-i folds.
   - If it contains a CJK run of 3+ chars, or the user asks for a substring: trigram MATCH.
   - If it contains a CJK run of 1–2 chars: `instr()` scan.
   - Otherwise: `unicode61` MATCH with the last token as a prefix.
   - If there are few or no hits: vocabulary plus rapidfuzz "did you mean", and optionally an automatic re-query with the corrected term.
6. **Runtime capability probe at startup.** Check `sqlite_version_info >= (3,45)` for trigram diacritics, `>= (3,43)` for contentless-delete, and that FTS5 exists (`CREATE VIRTUAL TABLE temp.x USING fts5(a)`). Fall back to LIKE scans with a logged warning, so Ubuntu 22.04 pip users get correct, slower search rather than an error.

### Gaps
- No user research or published study on cross-entity ranking preferences for qualitative-research tools was found.
- The type priors and RRF k above are conventional defaults, not tuned values.
