# Japanese glossary — research draft

Working notes for `bristlenose/locales/glossary.csv` ja seeding (Phase 1 of the
japanese-translation branch). Throwaway after Phase 1 lands.

## Conventions

- **Default register**: katakana for foreign-origin tech / UX terms (per
  design-i18n.md line 80: "the JA UXR community uses katakana for most
  foreign-origin terms"). Native Japanese only where (a) Apple+Microsoft both
  use it, (b) KJ法 lineage applies, or (c) the katakana would be obscure.
- **Long-vowel rule** (JTF / Apple): drop the trailing ー on three-mora-or-more
  loan-words ending in -er/-or/-ar (e.g. ユーザ vs ユーザー — Apple uses
  ユーザー with the long mark; we follow Apple). Modern Apple JA keeps the long
  mark; that's our default.
- **Punctuation**: full-width 「」 for quoted strings inside JA UI text,
  full-width 。 for terminal periods. Half-width Latin numerals.
- **Honorifics**: avoid です/ます chains in dense UI labels; use noun phrases
  (Apple HIG style). Use です/ます in help text and error messages.

## Tier 1 / 2 sources used

- **Apple JA Style Guide** + reading current macOS Sequoia / iOS 18 menus
  (System Settings, Mail, Finder) — chrome verbs and OS nouns.
- **Microsoft Language Portal** + MS Japanese Style Guide — cross-check, plus
  enterprise SaaS terms.
- **MAXQDA / NVivo / ATLAS.ti JA editions** — QDA core vocabulary.
- **HCD-Net (人間中心設計推進機構)** — UX/UXR concepts in ja research register.
- **KJ法** (Jiro Kawakita) — affinity-diagram lineage; where native Japanese
  reads more naturally than katakana for "theme/cluster/group".
- **design-i18n.md** — already-settled terms (発言 for Quote line 62; katakana
  for Don Norman line 106; sentiment loanwords line 80).

## Confidence column

- **high** — settled by Apple/MS or by an existing design-i18n.md decision.
  Two-or-more independent sources agree.
- **med** — one strong source, or katakana convention straightforward.
- **low** — needs native-speaker review before alpha. Flagged with `# review`
  in the `note` column. Don't over-anchor on these in the bulk pass.

## Rows

### Apple HIG verbs (chrome)

| English | Proposed JA | Alternatives | Confidence | Notes |
|---|---|---|---|---|
| Save | 保存 | セーブ | high | Apple HIG; MS agrees |
| Cancel | キャンセル | 取消 | high | Apple HIG (loanword) |
| Close | 閉じる | クローズ | high | Apple HIG |
| Copy | コピー | 複製 | high | Apple HIG (複製 = Duplicate, distinct) |
| Delete | 削除 | 消去 | high | Apple HIG |
| Undo | 取り消す | 元に戻す | high | Apple HIG. macOS Edit menu = "取り消す"; "元に戻す" used in iOS contexts |
| Redo | やり直す | 再実行 | high | Apple HIG Edit menu |
| Search | 検索 | サーチ | high | Apple HIG |
| Print | プリント | 印刷 | high | Apple HIG uses プリント; 印刷 still common in apps |
| Export | 書き出す | エクスポート | high | Apple HIG (verb form for File menu); エクスポート in noun/SaaS contexts |
| Import | 読み込む | インポート | high | Apple HIG; インポート in SaaS chrome |
| Settings | 設定 | 環境設定 | high | Apple HIG post-Ventura ("Settings" replaced "Preferences"; JA followed: "設定" replaced "環境設定") |
| Open | 開く | オープン | high | Apple HIG |
| Hide | 非表示 | 隠す | high | "非表示にする" common in app chrome; 隠す for menu actions |
| Show | 表示 | 見せる | high | Apple HIG |
| Accept | 承認 | 受け入れる | high | "承認" matches MS; "受け入れる" softer |
| Apply | 適用 | アプライ | high | Apple HIG |
| Reset | リセット | 初期化 | high | Apple HIG (リセット); 初期化 for "factory reset" register |
| Edit | 編集 | エディット | high | Apple HIG |
| Done | 完了 | 終了 | high | Apple HIG |
| OK | OK | 了解 | high | Apple HIG keeps "OK" Latin |
| Confirm | 確認 | 確定 | high | "確認" = confirm/check; "確定" = finalize |
| Continue | 続ける | 継続 | high | Apple HIG |
| Back | 戻る | バック | high | Apple HIG |
| Next | 次へ | ネクスト | high | Apple HIG |
| Skip | スキップ | 飛ばす | high | Apple HIG |
| Retry | やり直す | 再試行 | high | "再試行" common in error UI; "やり直す" matches Redo |
| Add | 追加 | 加える | high | Apple HIG |
| Remove | 削除 | 取り除く | high | Same as Delete in chrome |
| Refresh | 更新 | リフレッシュ | high | Apple HIG / MS |
| Loading… | 読み込み中… | ロード中… | high | Apple HIG |
| Error | エラー | 誤り | high | Universal loanword |
| Warning | 警告 | 注意 | high | Apple HIG |

### OS chrome nouns

| English | Proposed JA | Alternatives | Confidence | Notes |
|---|---|---|---|---|
| Window | ウインドウ | ウィンドウ | high | Apple uses ウインドウ (no small ィ) — distinctive Apple JA convention |
| Tab | タブ | — | high | Universal |
| Sidebar | サイドバー | — | high | Apple HIG |
| Toolbar | ツールバー | — | high | Apple HIG |
| Menu | メニュー | — | high | Universal |
| Help | ヘルプ | — | high | Apple HIG |
| About | ～について | About | high | Apple HIG: "Bristlenoseについて" pattern |
| Preferences | 環境設定 | 設定 | med | Pre-Ventura term; modern apps use 設定. Bristlenose targets modern macOS so use 設定 |
| Quit | 終了 | やめる | high | Apple HIG: app menu "Bristlenoseを終了" |
| File | ファイル | — | high | Apple HIG |
| Folder | フォルダ | フォルダー | high | Apple uses フォルダ (no long mark). MS uses フォルダー. Apple wins for desktop Mac app |
| Project | プロジェクト | 案件 | high | Universal SaaS loanword |

### Generic SaaS chrome

| English | Proposed JA | Alternatives | Confidence | Notes |
|---|---|---|---|---|
| Filter | フィルタ | フィルター | high | Apple uses フィルタ (Photos.app); MS uses フィルター. Match Apple |
| Sort | 並び替え | ソート | high | Apple HIG; ソート in dev contexts |
| Tag | タグ | — | high | Universal loanword (design-i18n.md table line 39) |
| Comment | コメント | — | high | Universal |
| Share | 共有 | シェア | high | Apple HIG |
| Download | ダウンロード | — | high | Universal |
| Upload | アップロード | — | high | Universal |
| Sync | 同期 | シンク | high | Apple HIG |
| Sign in / Log in | サインイン | ログイン | high | Apple HIG = サインイン. Microsoft = サインイン |
| Sign out / Log out | サインアウト | ログアウト | high | Mirrors sign-in choice |

### QDA / Bristlenose core nouns

| English | Proposed JA | Alternatives | Confidence | Notes |
|---|---|---|---|---|
| Code (QDA noun) | コード | — | high | design-i18n.md table line 37; MAXQDA JA |
| Codebook | コードブック | コードブック | high | design-i18n.md table line 38; MAXQDA JA |
| Quote (QDA) | 発言 | 引用 / クォート | high | design-i18n.md line 62 — "発言" anchored. 引用 = literary citation. クォート = generic loanword (avoid) |
| Session (interview) | セッション | インタビュー | high | design-i18n.md table line 41 |
| Interview | インタビュー | 面談 | high | UX register uses katakana (HCD-Net) |
| Participant | 参加者 | インタビュイー | high | HCD-Net standard. インタビュイー = interviewee (acceptable alt) |
| Researcher | 研究者 | リサーチャー | high | UX register uses both; Apple-tier formal is 研究者 |
| Observer | 観察者 | オブザーバー | high | "観察者" reads natural; "オブザーバー" in business-meeting register |
| Transcript | トランスクリプト | 文字起こし | high | "文字起こし" = literal "text transcription" — common; トランスクリプト = QDA-product register |
| Tag (QDA) | タグ | — | high | Same as chrome Tag |
| Theme | テーマ | 主題 | high | Universal (design-i18n.md line 68 confirms テーマ for "themes"); 主題 too literary |
| Topic | トピック | 話題 | high | Apple HIG: トピック |
| Cluster | クラスタ | クラスター / グループ | med | クラスタ matches Apple no-long-mark style. Could use グループ in KJ法 lineage but テーマ/グループ already taken |
| Section | セクション | 節 | high | Apple HIG = セクション; 節 too literary |
| Quotes (collection) | 発言 | 発言一覧 | high | Plural same as singular in JA |
| Sessions (collection) | セッション | — | high | Same; design-i18n.md line 41 |
| Signal (Bristlenose) | シグナル | — | high | design-i18n.md line 42, 68 — own concept, transliterate |
| Codes (collection) | コード | — | high | design-i18n.md line 37 |

### UX / UXR concepts (HCD-Net + UX TIMES + design-i18n.md)

| English | Proposed JA | Alternatives | Confidence | Notes |
|---|---|---|---|---|
| User | ユーザー | ユーザ | high | Apple keeps long mark; MS keeps long mark |
| User experience | ユーザーエクスペリエンス | UX | high | Wikipedia ja standard; full form for accessibility |
| User research | ユーザーリサーチ | ユーザー調査 | high | UX TIMES uses リサーチ; HCD-Net mixes |
| Usability | ユーザビリティ | 使いやすさ | high | HCD-Net standard; 使いやすさ for marketing copy only |
| Journey | ジャーニー | 道のり | high | UX register uses katakana (e.g. カスタマージャーニー) |
| Friction | フリクション | 摩擦 | med | UX TIMES uses katakana; 摩擦 reads physics-y. # review |
| Sentiment | 感情 | センチメント | high | HCD-Net: 感情. センチメント used in market research |
| Insight | インサイト | 洞察 | high | UX TIMES = インサイト; 洞察 too academic |
| Finding | 発見 | ファインディング | high | "発見" reads natural; "ファインディング" alternate in research-ops register |
| Pattern | パターン | — | high | Universal |
| Heuristic | ヒューリスティック | — | high | Universal Nielsen-era loan |

### Don Norman concepts (design-i18n.md line 106 — already settled)

| English | Proposed JA | Alternatives | Confidence | Notes |
|---|---|---|---|---|
| Affordance | アフォーダンス | — | high | design-i18n.md anchored; Wikipedia ja:アフォーダンス |
| Signifier | シグニファイア | — | high | design-i18n.md anchored |
| Mapping | マッピング | — | high | design-i18n.md anchored |
| Feedback | フィードバック | — | high | Universal |

### Sentiment vocabulary (enums.json)

| English | Proposed JA | Alternatives | Confidence | Notes |
|---|---|---|---|---|
| Frustration | フラストレーション | 不満 | high | UX register; 不満 = literal complaint |
| Confusion | 混乱 | コンフュージョン | high | Native Japanese reads natural here |
| Doubt | 疑念 | ダウト | high | Native Japanese; ダウト = card-game register |
| Surprise | 驚き | サプライズ | high | Native; サプライズ = party context |
| Satisfaction | 満足 | サティスファクション | high | Native; loanword unused |
| Delight | 喜び | ディライト | high | Native; ディライト = brand-name register |
| Confidence | 自信 | コンフィデンス | high | Native |

### Research methodology (Phase 1+, may not all hit JSON in Phase 2)

| English | Proposed JA | Alternatives | Confidence | Notes |
|---|---|---|---|---|
| Thematic analysis | テーマ分析 | 主題分析 | high | UX TIMES / academic standard |
| Open coding | オープンコーディング | 開放コーディング | high | MAXQDA JA / academic |
| Coding | コーディング | 符号化 | high | QDA standard; 符号化 = signal-processing register |
| Saturation (theoretical) | 理論的飽和 | サチュレーション | med | Academic ja; flagged for native review |
| Affinity diagram | 親和図 | アフィニティ図 | high | KJ法 lineage — native reads natural |
| Memo (QDA) | メモ | — | high | MAXQDA JA |
| Anonymisation | 匿名化 | アノニマイズ | high | Standard ja legal/data register |
| PII | 個人情報 | PII | high | Universal Japanese legal term |
| Pipeline | パイプライン | — | high | Engineering loanword |
| Stage | ステージ | 段階 | high | Apple HIG = ステージ in tech contexts; 段階 in process descriptions |
| Render | レンダリング | 描画 | high | Tech standard |
| Speaker | 話者 | スピーカー | high | "話者" is the linguistics/transcription standard. スピーカー = audio device |
| Heatmap | ヒートマップ | — | high | Universal |
| Tag group | タググループ | タグセット | high | Compound matches NVivo JA |
| Star (verb, favourite) | スターを付ける | お気に入り登録 | med | Apple Mail JA = スターを付ける. # review for nuance |

## Pause point

Locked rows: ~75. Confidence: 4 rows marked `# review` (low-confidence —
Friction, Saturation, Star verb, plus a re-check of "Confidence" sentiment
register).

Next: append to `bristlenose/locales/glossary.csv` and start Phase 2 with the
smallest namespace files. Any of the `# review` flagged rows the user wants to
hold for native review can be commented out before commit; for now they're
locked at our best guess so the bulk pass has anchors.
