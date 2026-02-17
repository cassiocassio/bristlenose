/** TypeScript interfaces mirroring the quotes API response models. */

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
