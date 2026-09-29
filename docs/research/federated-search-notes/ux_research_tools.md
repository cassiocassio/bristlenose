# Search in qualitative-research and user-research tools (as of Sep 2026)

Scope: Dovetail, Condens, Marvin (HeyMarvin), EnjoyHQ, Aurelius, Great Question, MAXQDA (+ Tailwind), NVivo, ATLAS.ti, Delve, Taguette, QualCoder, Reframer. Two families appear throughout and behave very differently:

- **CAQDAS desktop tools** (MAXQDA, NVivo, ATLAS.ti, QualCoder): search is an *analytic instrument* — a dialog with operators, a scope, a results table with context, and a "code all hits" exit. Per-project; no cross-project repository.
- **UXR repository SaaS** (Dovetail, Condens, Marvin, Great Question, Aurelius, EnjoyHQ): search is *navigation + retrieval* — a ⌘K box, faceted filters (project, tag, person, date), and since 2024 an AI "ask a question" mode with cited quotes. Cross-project by design, scoped by permissions.

Method note: roughly 30 search/fetch calls. Two Dovetail engineering blog URLs returned 404 at fetch time, and the Marvin press release and UserTesting's EnjoyHQ article returned 403. Claims from those sources rest on search-engine snippets and are marked. Reddit threads were not reachable through the search tool; user-complaint evidence comes from AWS Marketplace reviews of Dovetail (G2 was not fetchable).

---

## 1. What entities are searchable, and is it one search or one per view?

### Takeaway
Repository tools have **one global search box across object types** (projects, notes/docs, highlights, insights, tags, people), refined by type facets, plus per-view filters. Dovetail's Feb 2026 redesign made its default search **exclude tags, highlights, themes and contacts** to keep results focused. CAQDAS tools search **document text plus memos/comments** in a dialog, and find codes through a separate tree filter.

### Cited Findings
- **Dovetail, two surfaces.** Quick Search (⌘K/Ctrl+K) is for "recent interactions, navigate to content you know exists". Explore is "a visual search experience" across highlights, projects, conversations and customer moments. — [Dovetail help: Search](https://docs.dovetail.com/help/search)
- **Dovetail default scope.** Search indexes projects, folders, docs, notes and navigation items. Contacts, tags, highlights and themes are "excluded … to keep results focused on core content" unless a filter re-includes them. — [Dovetail help: Search](https://docs.dovetail.com/help/search)
- **Dovetail changelog, 12 Feb 2026.** "Streamlined default filtering (excludes contacts, tags, highlights, themes)". Navigation pages were added to Quick Search, and ranking was updated to "prioritize recent, relevant content based on object views". — [Dovetail changelog: Faster, simpler search](https://dovetail.com/changelog/faster-simpler-search-in-dovetail)
- **Dovetail Magic Search, Apr 2024 (older).** Surfaced results across "highlights, insights, and notes". — [Dovetail changelog: Magic search](https://dovetail.com/changelog/magic-search/)
- **Dovetail workspace tags.** A tag opened inside a project gets a default filter limiting highlights to that project. Removing the filter, or opening the tag as a page, shows the tag's highlights "across all linked projects". — [Dovetail blog: workspace tags](https://dovetail.com/blog/introducing-workspace-tags/) (search snippet)
- **Condens.** Global search lets users "type a keyword, and you can browse all relevant elements", filtering by "projects, sessions, tags, concrete highlights, participants, and Artifacts". — [Condens: Analyze across projects](https://condens.io/help/how-to-guides/best-practices/analyze-across-projects/)
- **Condens (June 2023, older).** Sessions, artifacts (findings/reports) and published artifacts in the Stakeholder Repository are searchable. Users can add highlights, tags, comments and metadata directly from search results, and batch-update sessions across projects. — [Condens product update: search](https://condens.io/product-updates/inside-condens-search-product-updates/)
- **Marvin.** Search surfaces "relevant notes, files and Insight reports across your repository", with filters for project, file tags, creation date, file type and creator. Ask AI is a distinct mode. — [Marvin help: Discover research](https://help.heymarvin.com/en/articles/10130469-discover-research-on-marvin)
- **Aurelius.** "Universal Search" finds "tags, notes, documents, recommendations, collections, and insights across projects". **Tag Groups** "act like a saved search based on your selected tags" and auto-update as new tagged items arrive. — [Aurelius features](https://www.aureliuslab.com/features) (search snippet)
- **EnjoyHQ (historic; now UserTesting-owned).** Separate filters to search "through all your data" and "through highlights or text snippets". — [GetApp: EnjoyHQ](https://www.getapp.com/customer-management-software/a/enjoyhq/) (search snippet). UserTesting's own help article ([Searching your data, projects and insights](https://help.usertesting.com/hc/en-us/articles/11880337839901-Searching-your-data-projects-and-insights)) returned 403.
- **Reframer (Optimal Workshop).** Observations can be filtered by the study member who wrote them and by starred status, alongside keyword search. Tags are described as "variables that you can use to filter your data later". The Themes tab offers tag-based analysis with filters. — [Optimal blog: 6 tips for Reframer](https://blog.optimalworkshop.com/6-tips-for-making-the-most-of-reframer/); [Optimal help: Reframer tags](https://support.optimalworkshop.com/en/articles/2626886-creating-and-managing-reframer-tags) (search snippets)
- **MAXQDA.** Text Search can search "In documents, In comments, In paraphrases, or In memos". It can also search only coded segments currently listed in the Retrieved Segments window. — [MAXQDA 2022 manual: Text Search options](https://www.maxqda.com/help-mx22/lexical-search/the-lexical-search-options-in-the-dialog-window) (search snippet)
- **NVivo.** Text Search query scope is all files and externals, selected items, or selected folders. Results include type-specific tabs for Text, Picture, Audio, Video and Survey. — [NVivo 15 help: Text search](https://help-nv.qsrinternational.com/15/win/Content/queries/text-search-query.htm)
- **QualCoder.** Code finding is a separate "Find Code" button that filters the code tree by name. Text auto-coding uses its own search box. — [QualCoder: Coding Text](https://qualcoder.org/doc/en/4.1.-Coding-Text/) (search snippet)
- **Great Question Ask AI.** Searches "transcripts and study summaries" at repository level, plus "that study's highlights" when scoped to a study or session. — [Great Question: Ask AI](https://greatquestion.co/support/repository/ask-ai)

### Inferences
- The industry default is one entry point with **type facets**. It is not one search per lens and not an undifferentiated blob.
- Dovetail's 2026 choice to *demote* highlights and tags from the default result set is notable. Highlights are high-volume and swamp navigation results, so a toolbar search that mixes "go to thing" with "find evidence" needs a way to separate them: sections, or a navigation-vs-evidence split like Quick Search vs Explore.
- Participants/contacts appear as a **facet** (Condens, Dovetail "Anyone"/contacts filter) more often than as primary results.

### Gaps
- No vendor documents a ranking formula beyond Dovetail's "recency + object views + keyword weighting" note.
- Whether Condens or Marvin keyword search matches inside transcript bodies and highlight text, or only in titles and metadata, was not confirmed from docs.

---

## 2. How are results grouped and ranked? KWIC? Jump to timecode or video?

### Takeaway
CAQDAS tools give **KWIC-style context** (sentence or n-words around the hit, or a word tree) and click-to-position in the document. Repository tools give **ranked lists by object type**. Their AI answers give **cited verbatim quotes that jump to the moment in the recording**; that jump is the de-facto 2025–26 standard.

### Cited Findings
- **MAXQDA results table.** Shows hits with document origin, a "Context" column (document, paragraph or sentence for combined searches) and hit counts. Clicking "opens the document and positions exactly where the reference is located. The search term found is highlighted." — [MAXQDA 2022 manual: Search Results](https://www.maxqda.com/help-mx22/lexical-search/search-results)
- **MAXQDA Extended Text Search.** Presents results as **sentences**, with boundaries defined by `. ? ! :`. — [MAXQDA help: Extended Text Search](https://www.maxqda.com/help/text-search/the-extended-lexical-search)
- **MAXQDA KWIC** (word-frequency tools, via a methods summary). Users can "specify the number of words to include before and after keywords" and export to HTML/Excel. — [SMU KWIC analysis guide (2020)](https://people.smu.edu/mcairns/files/2020/04/KWIC-Analysis-Guide-NC-1.pdf) (search snippet; older)
- **MAXQDA re-runs.** Earlier searches can be reopened from the Analysis menu without re-running, and documents with hits can be "activated" for downstream analysis. — [MAXQDA 2022 manual: Search Results](https://www.maxqda.com/help-mx22/lexical-search/search-results)
- **NVivo result tabs.** **Summary** (files containing the term), **Reference** (the phrase with narrow context, expandable), and **Word Tree** (lead-in and lead-out branches, font size by frequency). — [NVivo 15 help](https://help-nv.qsrinternational.com/15/win/Content/queries/text-search-query.htm)
- **NVivo "Spread to".** Widens the coded context around each hit, but "if you choose to spread coding, you cannot view the results as a word tree". — [NVivo help (older versions)](https://help-nv11mac.qsrinternational.com/desktop/procedures/run_a_text_search_query.htm) (search snippet)
- **ATLAS.ti.** Results display in a **Quotation Reader** showing where matches occur *and existing codes*, with small or large preview. Base units are paragraph, sentence, word or exact match. — [ATLAS.ti 25 manual: Search Text and Auto-code](https://manuals.atlasti.com/Win/en/manual/SearchAndCode/SearchAndCodeTextSearch.html)
- **Dovetail ranking.** Relevance by default, with Created, Updated or Name as alternatives. Pressing Enter on a keyword search "opens the best match". AI summaries auto-trigger for question-phrased queries. — [Dovetail help: Search](https://docs.dovetail.com/help/search); [Dovetail changelog Feb 2026](https://dovetail.com/changelog/faster-simpler-search-in-dovetail)
- **Dovetail AI citations.** "Every response is evidence-backed with deep-linked citations to the exact moment, quote, or artifact in your workspace." — [Dovetail: AI Chat & Search](https://dovetail.com/product/ai-chat-and-search/) (search snippet)
- **Great Question citations.** Answers include "verbatim quotes with full source attribution, session ID, study name, date, and participant context". Users can "click any quote block to jump directly to that moment in the recording". — [Great Question: Ask AI](https://greatquestion.co/support/repository/ask-ai)
- **Delve.** "Good interactivity between the list of results and the main interface" in its Search panel. — CAQDAS Networking Project review of Delve (Surrey, Mar 2020, older), via search snippet; the [PDF](https://www.surrey.ac.uk/sites/default/files/2020-04/delve-distinguishing-features-march-2020.pdf) was not machine-readable.
- **User complaint (Dovetail).** "Search is powerful, but the results are presented in an unstructured manner that has limited options for quickly filtering down." — [AWS Marketplace Dovetail reviews](https://aws.amazon.com/marketplace/reviews/reviews-list/prodview-ckaqbf4iqi5mi) (search snippet; exact reviewer and date not recovered)

### Inferences
- For transcript hits, researchers expect **sentence-level context with the term highlighted** and **click → exact position** (text position in CAQDAS; timecode in video-first tools).
- Showing **existing codes alongside each hit** (ATLAS.ti Quotation Reader) is a useful precedent for Bristlenose: tags and sentiment shown next to a matched quote.
- Grouping by object type plus faceting is the norm. The main complaint is not ranking; it is **lack of structure and fast narrowing**.

### Gaps
- No source describes Marvin's or Condens's keyword result snippet format (KWIC or not), nor whether a keyword hit in a transcript deep-links to its timestamp outside AI answers.

---

## 3. Operators, stemming, synonyms, and "search & code" workflows

### Takeaway
CAQDAS tools carry the full operator set: boolean, NEAR/proximity, wildcards, phrase, regex, stemming and synonyms, with NVivo adding generalisation and specialisation. They all end in **bulk-code the hits**. Repository SaaS exposes little beyond quoted phrases and filters, and pushes intent matching to AI.

### Cited Findings
- **NVivo five-level "Find" slider.** Exact; plus stemmed ("farm" → farming, farmed); plus synonyms; plus specialisations ("scallops" for "fish"); plus generalisations ("agriculture" for "farming").
  - Operators: AND/OR/NOT, NEAR, `*` wildcard, `~` fuzzy, quoted phrase. Wildcards and fuzzy restrict matching to exact.
  - Results can be **saved as codes or cases**, merged into existing codes, and chained into compound queries.
  - — [NVivo 15 help](https://help-nv.qsrinternational.com/15/win/Content/queries/text-search-query.htm)
- **MAXQDA Extended Text Search.** AND / OR / NOT groups; `?` single character, `*` wildcard; `<(word)` and `(word)>` word-boundary anchors; quoted phrases; case-sensitive option. — [MAXQDA help: Extended Text Search](https://www.maxqda.com/help/text-search/the-extended-lexical-search)
- **MAXQDA basic search.** "Find whole words", case-sensitive, regex. AND requires terms "within a defined distance of each other in an adjustable search range". — [MAXQDA 2022 manual: options](https://www.maxqda.com/help-mx22/lexical-search/the-lexical-search-options-in-the-dialog-window) (search snippet)
- **MAXQDA autocode.** "Autocode search results" with existing or new codes, respecting per-row exclusion (Stop) marks. Export to Excel, HTML, Word, RTF or TSV. — [MAXQDA 2022 manual: Search Results](https://www.maxqda.com/help-mx22/lexical-search/search-results)
- **ATLAS.ti Search & Code.** Four search types: Text Search, Named Entity Recognition, Sentiment Analysis, and Find Concepts, plus Expert Search (regex) and AI Coding.
  - Text Search offers synonyms in 8 languages, inflected forms ("run" → running, ran), `*` wildcards, quoted phrase, and AND/OR scoped to sentence or paragraph.
  - Bulk-coding: select all results and apply one code.
  - — [ATLAS.ti 25 manual](https://manuals.atlasti.com/Win/en/manual/SearchAndCode/SearchAndCodeTextSearch.html)
- **QualCoder.** Exact-match auto-code accepts `|` alternation ("politics|politicians"). — [QualCoder: Coding Text](https://qualcoder.org/doc/en/4.1.-Coding-Text/) (search snippet)
- **Dovetail.** Exact matching uses quotation marks; otherwise natural language. — [Dovetail help: Search](https://docs.dovetail.com/help/search)
- **Condens (2023).** Supports "complex queries, searching for multiple keywords, applying filters, changing sorting options". Stakeholders can likewise "build queries". — [Condens product update](https://condens.io/product-updates/inside-condens-search-product-updates/)

### Inferences
- "Search & code", meaning search results as a workbench for bulk tagging, is a **core CAQDAS expectation** and a gap in most UXR repositories. Condens's "add highlights and tags directly from search results" is the closest repository analogue.
- Operators matter to methods-trained (academic) users. UXR users mostly rely on phrase quotes plus facets. A reasonable minimum: `"exact phrase"`, stemming on by default with a way to force exact, and facet chips for tag, participant and session.

### Gaps
- No evidence on how often researchers actually use NEAR, regex or generalisation levels. Usage data is absent.

---

## 4. Semantic / AI search: implementation, and how researchers rate it

### Takeaway
All major tools now pair keyword search with an **LLM "ask" mode grounded by retrieval, returning cited verbatim quotes**. Dovetail describes Magic Search as hybrid full-text plus semantic. QualCoder is the only one publishing concrete internals: E5 embeddings in FAISS, BM25 in SQLite, and regex. Vendors themselves admit semantic search surfaces "related-but-off-point" content. The trust mechanism everyone converges on is **click-through to the exact source moment**.

### Cited Findings
- **Dovetail Magic Search.** Uses "a hybrid search process that combines full-text (keyword-based) search with semantic search", matching on concepts rather than keywords, with auto-generated summaries of related highlights. "Every point generated … is backed up by evidence." — [Dovetail blog: How we built AI — magic search & Ask Dovetail](https://dovetail.com/blog/how-we-built-ai-in-dovetail-magic-search-and-ask-dovetail/) (search snippet only; page 404'd at fetch time); [Dovetail changelog Apr 2024](https://dovetail.com/changelog/magic-search/)
- **Dovetail AI model.** "Uses a generic AI model and doesn't feed it any training data." — [Dovetail help: Dovetail AI](https://docs.dovetail.com/help/dovetail-ai) (search snippet)
- **Dovetail current behaviour.** AI summaries auto-appear for question-style queries (Enterprise). The query "carries over" into Chat. Slack/Teams querying is available on Enterprise. — [Dovetail help: Search](https://docs.dovetail.com/help/search)
- **Dovetail MCP.** An MCP server lets external AI models "access and search your Dovetail workspace". — [Dovetail developers: MCP](https://developers.dovetail.com/docs/mcp)
- **Great Question MCP.** Also markets MCP access to its repository. — [Great Question blog: MCP for user research](https://www.greatquestion.com/blog/mcp-for-user-research) (search snippet)
- **Great Question Ask AI.** Described as "an agentic system … not just a keyword search tool" using "semantic understanding to match intent".
  - Quotes are validated "word-for-word against the transcript before it's used".
  - Stated limitations: untranscribed sessions and non-spoken methods are not searchable; "very large accounts may be slower"; speaker role detection "occasionally misassigns speakers"; semantic search "occasionally surfaces related-but-off-point content".
  - — [Great Question: Ask AI](https://greatquestion.co/support/repository/ask-ai)
- **Marvin (Jan 2026).** Launched "Agentic Ask AI" whose agents "break down questions, cross-validate findings, and surface evidence-backed insights". Slack `/heymarvin` searches the whole repository. — [BusinessWire, 27 Jan 2026](https://www.businesswire.com/news/home/20260127667920/en/HeyMarvin-Launches-Industrys-First-Agentic-AI-Search-for-Customer-Research) (search snippet; page 403'd)
- **Marvin guidance.** Recommends "asking specific questions and using filters to search within relevant projects" to improve answers. — [Marvin help](https://help.heymarvin.com/en/articles/10130469-discover-research-on-marvin)
- **ATLAS.ti Conversational AI.** Uses OpenAI GPT models over **user-selected documents**, not a retrieval index over the project. Answers include "linked references to supporting quotations", with a bulk "Code all references" action.
  - Documented limits: it "does not automatically understand document names, document groups, or existing coding structures" and "may occasionally generate incomplete or inaccurate interpretations".
  - Data goes to US-based servers; OpenAI does not train on it.
  - — [ATLAS.ti help: Conversational AI](https://atlastihelp.helpscoutdocs.com/article/612-conversational-ai)
- **ATLAS.ti "Find Concepts".** A Search & Code option alongside NER and sentiment; mechanism not documented on the fetched page. — [ATLAS.ti 25 manual](https://manuals.atlasti.com/Win/en/manual/SearchAndCode/SearchAndCodeTextSearch.html)
- **QualCoder (open source).** "Hybrid system based on E5 sentence encoder embeddings stored in a FAISS vector store for semantic search, and a SQLite BM25 index for fast keyword retrieval", plus regex available to its AI agent.
  - Embedding runs locally (~2.5 GB model), once per document, in a background thread, redone on edit.
  - Only "a small number of selected text chunks, each about 500 characters long, are sent to the cloud".
  - — [QualCoder docs: AI Setup](https://qualcoder.org/doc/en/2.3.-AI-Setup/)
  - An older version described a chroma_db-based vector store; the docs now say FAISS. — [same page (search snippet)](https://qualcoder.org/doc/en/2.3.-AI-Setup/)
- **MAXQDA Tailwind.** A standalone AI web app that identifies topics "across all your files" with "semantic grouping". Cross-project semantic search is not documented. — [MAXQDA Tailwind features](https://www.maxqda.com/maxqda-tailwind/features/) (search snippet)
- **Researcher rating (Dovetail review, Apr 2026).** "heard from my fellow researchers that the AI chat wasn't very accurate, though I didn't encounter that problem myself". — [AWS Marketplace Dovetail reviews p.5](https://aws.amazon.com/marketplace/reviews/reviews-list/prodview-ckaqbf4iqi5mi?page=5)
- **Academic (arXiv 2025).** Senior UX practitioners "pointed out the absence of evidence and emphasized the need for verification", while junior practitioners "often lacked familiarity with the concept of hallucination". — [UXer-AI Collaboration Process for Enhancing Trust](https://arxiv.org/pdf/2510.11087) (search snippet)
- **Vendor-blog advice (CleverX).** The most reliable hallucination check is "timestamp or line-number verification": require the tool to cite exact transcript locations, then spot-check. — [CleverX blog](https://cleverx.com/blog/ai-hallucination-in-research-analysis-real-risks/) (search snippet; vendor content, moderate reliability)

### Inferences
- Architecture consensus: **hybrid lexical plus embedding retrieval → LLM synthesis → verbatim, validated citations with deep links**. Great Question's word-for-word quote validation is the strongest published guard against invented quotes.
- The typical failure is **recall and precision on exact phrases**. Semantic search drifts "off-point", and ATLAS.ti's chat ignores codes and document metadata. That is why every vendor keeps keyword search and phrase quoting alongside AI.
- Dovetail's "question-shaped query ⇒ AI summary; keyword ⇒ jump to best match" is a neat mode switch **inside one box**, avoiding a separate AI surface.

### Gaps
- No published recall/precision evaluation of any vendor's semantic search was found.
- The Dovetail engineering blog (embedding model, vector store, reranker) could not be fetched. Only the "hybrid" characterisation is sourced.
- Reddit r/UXResearch and ResearchOps Slack threads were not retrievable, so community sentiment on AI search is thinly sourced.

---

## 5. Cross-project / repository search: scoping, permissions, provenance

### Takeaway
Repository tools are **cross-project by default**, with a project/folder scope filter. Results are **permission-trimmed**: you see only what you can access. The top user request is the reverse of Bristlenose's concern: **scope a search down to one project**. CAQDAS tools have no cross-project search at all.

### Cited Findings
- **Dovetail filters.** "Anywhere – Restrict results to specific channels, projects, or folders"; also Anyone, Anytime and Title only. — [Dovetail help: Search](https://docs.dovetail.com/help/search)
- **Dovetail permissions.** Folder-level permissions inherit to child folders, channels and projects, and can be restricted per item. Roles are Manager, Contributor and Viewer, with Enterprise user groups. — [Dovetail help: Access and permissions](https://docs.dovetail.com/help/access-and-permissions) (search snippet)
- **Dovetail contacts.** Access controls exist on the Contacts database. — [Dovetail changelog: Access controls to Contacts](https://dovetail.com/help/changelog/access-controls-to-contacts-database/) (title only)
- **User requests on scoping (Dovetail).**
  - "The only thing I'd change … is being able to search keywords within a specific project. Right now, I can only search site-wide." — Patrick M., Research, 8 Oct 2025, [AWS Marketplace reviews](https://aws.amazon.com/marketplace/reviews/reviews-list/prodview-ckaqbf4iqi5mi?page=1)
  - A snippet reports search "now feels harder to find what they need across projects", and that as more projects are added "the repository feels messier and more cluttered". — [AWS Marketplace reviews](https://aws.amazon.com/marketplace/reviews/reviews-list/prodview-ckaqbf4iqi5mi) (search snippet)
  - Note: the Feb 2026 "Anywhere" filter may post-date or address the Oct 2025 complaint.
- **Marvin.** "You'll see search results based on the information to which you have access". Cross-project published insights are visible "if admin settings permit broader exploration". — [Marvin help](https://help.heymarvin.com/en/articles/10130469-discover-research-on-marvin)
- **Great Question.** Ask AI "respects all existing team permissions and study visibility settings", and users can multi-select teams, studies or sessions as sources. Chat history is private to the user. — [Great Question: Ask AI](https://greatquestion.co/support/repository/ask-ai)
- **Great Question provenance.** Each quote carries session ID, study name, date and participant context. — [same](https://greatquestion.co/support/repository/ask-ai)
- **Condens.** Global tags span projects. Stakeholders search only the published Stakeholder Repository, with filters and queries. — [Condens: Global Tags](https://condens.io/help/using-condens/research-repository-functionality/connecting-data-across-projects-with-global-tags/) (search snippet); [Condens product update 2023](https://condens.io/product-updates/inside-condens-search-product-updates/)
- **Aurelius.** Universal Search is "across projects". — [Aurelius features](https://www.aureliuslab.com/features) (search snippet)

### Inferences
- The permission model in SaaS (per-folder/project access plus role) is the analogue of Bristlenose's "folder ≈ client" boundary. Nobody offers an explicit "don't cross clients" affordance because **access control does that job**.
- A local, single-user app has no ACL to lean on. The folder boundary therefore has to be **the scope default**, visible in the UI, with widening as a deliberate act. That matches the Dovetail "Anywhere" chip pattern.
- Provenance on every cross-project hit (project → session → participant code → timecode) is table stakes. Great Question's attribution line is the clearest example.
- The strongest user demand is **narrowing** (current project first), not broadening. "Current project" is a sensible default scope for a toolbar search.

### Gaps
- No vendor documents cross-*organisation* or cross-*client* confidentiality controls in search beyond ACLs.
- No agency-oriented tool with per-client partitions was found in this pass.

---

## 6. Participant privacy in search: redaction, PII, anonymised IDs

### Takeaway
Privacy is handled **upstream of search** (redaction at ingest) or **at the AI boundary** (PII masking, speaker handles). Almost no tool documents how redaction interacts with the search index. Condens has the richest redaction (text, audio, video). Great Question explicitly shows handles, never real names, in AI output.

### Cited Findings
- **Condens redaction.** Covers video (face, name-tag or full blur), audio (voice anonymisation, muting) and text (transcripts and notes).
  - "Auto-apply" or "Suggest" modes. Detected categories include names, DOB, age, nationality, SSN, phone, email, banking, card numbers and organisation names.
  - Workspace-wide rules apply to future uploads; existing recordings need manual processing.
  - Interaction with search is **not documented**.
  - — [Condens help: Data anonymization](https://condens.io/help/security-and-privacy/security-and-privacy-features/data-anonymization/)
- **Great Question.** "Speaker identification uses handles only. Real names never surface in AI responses", including highlight reels and chat. PII is masked from AI. — [Great Question: Ask AI](https://greatquestion.co/support/repository/ask-ai)
- **QualCoder.** Recommends users anonymise data before cloud AI analysis, and minimises cloud exposure to ~500-character chunks chosen by local retrieval. — [QualCoder docs: AI Setup](https://qualcoder.org/doc/en/2.3.-AI-Setup/)
- **Dovetail.** No native redaction documentation was found in this pass. Third parties sell add-on anonymisation for Dovetail spaces. — [Swiftask: Dovetail anonymization](https://swiftask.ai/ai-integration/dovetail/data-anonymization) (third-party marketing)
- **ATLAS.ti.** Conversational AI uploads selected document content to ATLAS.ti and OpenAI (US servers), which users must explicitly accept. — [ATLAS.ti help](https://atlastihelp.helpscoutdocs.com/article/612-conversational-ai)

### Inferences
- Two gaps nobody documents:
  1. Whether **redacted originals remain searchable**. An index built before redaction could leak a name via a hit snippet.
  2. Whether participant **real names** are searchable while displayed as codes.
- For Bristlenose, where p1/m1 codes and a people file map to names, a search design must decide:
  - Does typing a real name find p3? Useful to the researcher, and a re-identification vector in shared or exported contexts.
  - Snippets must render from the **redacted** text, never the pre-redaction source.
- "Handles only in AI output" (Great Question) is a clean precedent for keeping codes in any assistant/MCP search surface.

### Gaps
- No source on whether any tool excludes PII-flagged spans from the search index, or on audit logging of searches.
- No reliable Dovetail-native redaction documentation was found. It may exist but was not surfaced.

---

## 7. What researchers complain about or ask for

### Takeaway
Thin but consistent evidence:
- they want **project scoping and fast narrowing**;
- they find repository results **unstructured and cluttered at scale**;
- they **distrust AI answers** without verification.

Vendors' own docs concede semantic "off-point" results and advise users to add filters.

### Cited Findings
- Keyword search limited to site-wide, and a wish to narrow to one project. — [AWS Marketplace Dovetail review, Oct 2025](https://aws.amazon.com/marketplace/reviews/reviews-list/prodview-ckaqbf4iqi5mi?page=1)
- "Unstructured" results with "limited options for quickly filtering down", "insufficient filtering and logic", and repository "messier and more cluttered" as it grows. — [AWS Marketplace Dovetail reviews](https://aws.amazon.com/marketplace/reviews/reviews-list/prodview-ckaqbf4iqi5mi) (search-engine summary of multiple pages; individual attributions not recovered)
- AI chat reportedly "wasn't very accurate" (Apr 2026). A repository set up earlier "has become difficult to use" after frequent product changes (Apr 2026). — [AWS Marketplace p.5](https://aws.amazon.com/marketplace/reviews/reviews-list/prodview-ckaqbf4iqi5mi?page=5)
- Vendor-admitted limits: semantic search "occasionally surfaces related-but-off-point content"; speaker misassignment. — [Great Question: Ask AI](https://greatquestion.co/support/repository/ask-ai)
- Marvin advises filters and specific questions to get better AI answers. — [Marvin help](https://help.heymarvin.com/en/articles/10130469-discover-research-on-marvin)
- Delve users praise the ability to "search within all interview transcripts for specific words or phrases" and to "instantly find the perfect quote". — [Capterra: Delve](https://www.capterra.com/p/196428/Delve/) (search snippet)

### Inferences
- The valued core is simple: **find the exact quote fast, in context, and jump to it**. AI is valued for synthesis but checked against that core.
- Scale kills repositories. A global search that stays useful needs strong facets (type, project, tag, participant, date) and sensible defaults that suppress high-volume types.

### Gaps
- r/UXResearch, ResearchOps community and G2 threads could not be retrieved, so complaint evidence is mostly one vendor's (Dovetail's) marketplace reviews. Treat it as indicative, not representative.
- No survey data on how researchers split keyword vs AI search usage.
