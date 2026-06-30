export type SearchResultSource = {
  virtual_window_id?: string | null;
  title?: string;
  tags?: string[];
  folder_path?: string;
  provider?: string;
  kind?: string;
};

export type SearchResult = {
  id: string;
  index: string;
  score: number | null;
  snippet: string;
  source: SearchResultSource;
};

export type SearchResponse = {
  query: string;
  results: SearchResult[];
};

export type TerminalRecent = {
  window_id: string;
  title: string;
  todo_title?: string | null;
  last_used_at: string;
};

export type GlobalTerminalRecent = TerminalRecent & {
  client_id: string;
  client_name: string;
};

export type TerminalRecentPage = {
  items: TerminalRecent[];
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
};

export type GlobalTerminalRecentPage = Omit<TerminalRecentPage, "items"> & {
  items: GlobalTerminalRecent[];
};
