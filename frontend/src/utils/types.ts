/** TypeScript interfaces mirroring API response models. */

// ---------------------------------------------------------------------------
// Dashboard API
// ---------------------------------------------------------------------------

export interface StatsResponse {
  session_count: number;
  total_duration_seconds: number;
  total_duration_human: string;
  total_words: number;
  quotes_count: number;
  sections_count: number;
  themes_count: number;
  ai_tags_count: number;
  user_tags_count: number;
}

export interface DashboardSpeakerResponse {
  speaker_code: string;
  name: string;
  role: string;
}

export interface DashboardSessionResponse {
  session_id: string;
  session_number: number;
  session_date: string | null;
  duration_seconds: number;
  duration_human: string;
  speakers: DashboardSpeakerResponse[];
  source_filename: string;
  has_media: boolean;
  sentiment_counts: Record<string, number>;
}

export interface FeaturedQuoteResponse {
  dom_id: string;
  text: string;
  participant_id: string;
  session_id: string;
  speaker_name: string;
  start_timecode: number;
  end_timecode: number;
  sentiment: string | null;
  intensity: number;
  researcher_context: string | null;
  rank: number;
  has_media: boolean;
  is_starred: boolean;
  is_hidden: boolean;
}

export interface NavItem {
  label: string;
  anchor: string;
}

export interface DashboardResponse {
  stats: StatsResponse;
  sessions: DashboardSessionResponse[];
  featured_quotes: FeaturedQuoteResponse[];
  sections: NavItem[];
  themes: NavItem[];
  moderator_header: string;
  observer_header: string;
}

// ---------------------------------------------------------------------------
// Quotes API
// ---------------------------------------------------------------------------

export interface TagResponse {
  name: string;
  codebook_group: string;
  colour_set: string;
  colour_index: number;
}

export interface ProposedTagBrief {
  id: number;
  tag_name: string;
  group_name: string;
  colour_set: string;
  colour_index: number;
  confidence: number;
  rationale: string;
}

export interface QuoteResponse {
  dom_id: string;
  text: string;
  verbatim_excerpt: string;
  participant_id: string;
  session_id: string;
  speaker_name: string;
  start_timecode: number;
  end_timecode: number;
  sentiment: string | null;
  intensity: number;
  researcher_context: string | null;
  quote_type: string;
  topic_label: string;
  is_starred: boolean;
  is_hidden: boolean;
  edited_text: string | null;
  tags: TagResponse[];
  deleted_badges: string[];
  proposed_tags: ProposedTagBrief[];
  segment_index: number;
}

export interface SectionResponse {
  cluster_id: number;
  screen_label: string;
  description: string;
  display_order: number;
  quotes: QuoteResponse[];
}

export interface ThemeResponse {
  theme_id: number;
  theme_label: string;
  description: string;
  quotes: QuoteResponse[];
}

export interface QuotesListResponse {
  sections: SectionResponse[];
  themes: ThemeResponse[];
  total_quotes: number;
  total_hidden: number;
  total_starred: number;
}

// ---------------------------------------------------------------------------
// Codebook API
// ---------------------------------------------------------------------------

export interface CodebookTagResponse {
  id: number;
  name: string;
  count: number;
  colour_index: number;
}

export interface CodebookGroupResponse {
  id: number;
  name: string;
  subtitle: string;
  colour_set: string;
  order: number;
  tags: CodebookTagResponse[];
  total_quotes: number;
  is_default: boolean;
  framework_id: string | null;
}

export interface CodebookResponse {
  groups: CodebookGroupResponse[];
  ungrouped: CodebookTagResponse[];
  all_tag_names: string[];
}

export interface TemplateTagOut {
  name: string;
  colour_set: string;
  colour_index: number;
}

export interface TemplateGroupOut {
  name: string;
  subtitle: string;
  colour_set: string;
  tags: TemplateTagOut[];
}

export interface TemplateOut {
  id: string;
  title: string;
  author: string;
  description: string;
  author_bio: string;
  author_links: { label: string; url: string }[];
  groups: TemplateGroupOut[];
  enabled: boolean;
  imported: boolean;
}

export interface TemplateListResponse {
  templates: TemplateOut[];
}

export interface RemoveFrameworkInfo {
  tag_count: number;
  quote_count: number;
}

// ---------------------------------------------------------------------------
// Transcript page API
// ---------------------------------------------------------------------------

export interface TranscriptSpeakerResponse {
  code: string;
  name: string;
  role: string;
}

export interface TranscriptSegmentResponse {
  speaker_code: string;
  start_time: number;
  end_time: number;
  text: string;
  html_text: string | null;
  is_moderator: boolean;
  is_quoted: boolean;
  quote_ids: string[];
  segment_index: number;
}

export interface QuoteAnnotationResponse {
  label: string;
  label_type: string;
  sentiment: string;
  participant_id: string;
  start_timecode: number;
  end_timecode: number;
  verbatim_excerpt: string;
  tags: TagResponse[];
  deleted_badges: string[];
}

export interface TranscriptPageResponse {
  session_id: string;
  session_number: number;
  duration_seconds: number;
  has_media: boolean;
  project_name: string;
  report_filename: string;
  speakers: TranscriptSpeakerResponse[];
  segments: TranscriptSegmentResponse[];
  annotations: Record<string, QuoteAnnotationResponse>;
}

// ---------------------------------------------------------------------------
// AutoCode API
// ---------------------------------------------------------------------------

export interface AutoCodeJobStatus {
  id: number;
  framework_id: string;
  status: "pending" | "running" | "completed" | "failed" | "cancelled";
  total_quotes: number;
  processed_quotes: number;
  proposed_count: number;
  error_message: string;
  llm_provider: string;
  llm_model: string;
  input_tokens: number;
  output_tokens: number;
  started_at: string;
  completed_at: string | null;
}

export interface ProposedTagResponse {
  id: number;
  quote_id: number;
  dom_id: string;
  session_id: string;
  speaker_code: string;
  start_timecode: number;
  quote_text: string;
  tag_definition_id: number;
  tag_name: string;
  group_name: string;
  colour_set: string;
  colour_index: number;
  confidence: number;
  rationale: string;
  status: "pending" | "accepted" | "denied";
}

export interface ProposalsListResponse {
  proposals: ProposedTagResponse[];
  total: number;
}

// ---------------------------------------------------------------------------
// Tag-based analysis API
// ---------------------------------------------------------------------------

export interface TagSignalQuote {
  text: string;
  participant_id: string;
  session_id: string;
  start_seconds: number;
  intensity: number;
  tag_names: string[];
  segment_index: number;
}

export interface TagSignal {
  location: string;
  source_type: "section" | "theme";
  group_name: string;
  colour_set: string;
  count: number;
  participants: string[];
  n_eff: number;
  mean_intensity: number;
  concentration: number;
  composite_signal: number;
  confidence: "strong" | "moderate" | "emerging";
  quotes: TagSignalQuote[];
}

export interface AnalysisMatrixCell {
  count: number;
  weighted_count: number;
  participants: Record<string, number>;
  intensities: number[];
}

export interface AnalysisMatrix {
  cells: Record<string, AnalysisMatrixCell>;
  row_totals: Record<string, number>;
  col_totals: Record<string, number>;
  grand_total: number;
  row_labels: string[];
}

export interface SourceBreakdown {
  accepted: number;
  pending: number;
  total: number;
}

export interface TagAnalysisResponse {
  signals: TagSignal[];
  section_matrix: AnalysisMatrix;
  theme_matrix: AnalysisMatrix;
  total_participants: number;
  columns: string[];
  participant_ids: string[];
  source_breakdown: SourceBreakdown;
  trade_off_note: string;
}

// ---------------------------------------------------------------------------
// Per-codebook analysis API
// ---------------------------------------------------------------------------

export interface CodebookAnalysis {
  codebook_id: string;
  codebook_name: string;
  colour_set: string;
  signals: TagSignal[];
  section_matrix: AnalysisMatrix;
  theme_matrix: AnalysisMatrix;
  columns: string[];
  participant_ids: string[];
  source_breakdown: SourceBreakdown;
  tag_colour_indices: Record<string, number>;
}

export interface CodebookAnalysisListResponse {
  codebooks: CodebookAnalysis[];
  total_participants: number;
  trade_off_note: string;
}

// ---------------------------------------------------------------------------
// Sentiment analysis (baked into HTML as BRISTLENOSE_ANALYSIS global)
// ---------------------------------------------------------------------------

export interface SentimentSignalQuote {
  text: string;
  pid: string;
  sessionId: string;
  startSeconds: number;
  intensity: number;
  segmentIndex: number;
}

export interface SentimentSignal {
  location: string;
  sourceType: "section" | "theme";
  sentiment: string;
  count: number;
  participants: string[];
  nEff: number;
  meanIntensity: number;
  concentration: number;
  compositeSignal: number;
  confidence: "strong" | "moderate" | "emerging";
  quotes: SentimentSignalQuote[];
}

export interface SentimentMatrixCell {
  count: number;
}

export interface SentimentMatrix {
  cells: Record<string, SentimentMatrixCell>;
  rowTotals: Record<string, number>;
  colTotals: Record<string, number>;
  grandTotal: number;
  rowLabels: string[];
}

export interface SentimentAnalysisData {
  signals: SentimentSignal[];
  sectionMatrix: SentimentMatrix;
  themeMatrix: SentimentMatrix;
  totalParticipants: number;
  sentiments: string[];
  participantIds: string[];
}
