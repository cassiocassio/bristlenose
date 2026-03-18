/** Shared types for About modal sections. */

export interface EndpointInfo {
  label: string;
  url: string;
  description: string;
}

export interface DesignItem {
  label: string;
  url: string;
}

export interface DesignSectionData {
  heading: string;
  items: DesignItem[];
}

export interface DevInfoResponse {
  db_path: string;
  table_count: number;
  endpoints: EndpointInfo[];
  design_sections?: DesignSectionData[];
}
