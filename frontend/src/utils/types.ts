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
}

export interface CodebookResponse {
  groups: CodebookGroupResponse[];
  ungrouped: CodebookTagResponse[];
  all_tag_names: string[];
}
