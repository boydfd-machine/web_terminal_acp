import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useState } from "react";

import { fetchAgentRecordChat, fetchAgentRecordDetail, searchWindowAgentRecord } from "../api";
import type { AgentChatRoleFilter, AgentRecordDisplayMode } from "../types";

export const AGENT_RECORD_CHAT_PAGE_SIZE = 30;
export const AGENT_RECORD_DETAIL_PAGE_SIZE = 100;
export const AGENT_RECORD_SEARCH_PAGE_SIZE = 25;
type AgentRecordPageOffset = { chatOffset?: number; detailOffset?: number };

type UseAgentRecordDataOptions = {
  clientId: string | null;
  windowId: string | null;
  enabled: boolean;
};

export type AgentRecordDataState = ReturnType<typeof useAgentRecordData>;

export function useAgentRecordData({ clientId, windowId, enabled }: UseAgentRecordDataOptions) {
  const [mode, setMode] = useState<AgentRecordDisplayMode>("chat");
  const [chatRoleFilter, setChatRoleFilter] = useState<AgentChatRoleFilter>("all");
  const [chatPage, setChatPage] = useState(0);
  const [detailPage, setDetailPage] = useState(0);
  const [expanded, setExpanded] = useState(false);
  const [jumpRequest, setJumpRequest] = useState<{ sessionId: string; originMessageId?: string } | null>(null);
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null);
  const [searchDraft, setSearchDraft] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [searchPage, setSearchPage] = useState(0);

  useEffect(() => {
    setMode("chat");
    setChatRoleFilter("all");
    setChatPage(0);
    setDetailPage(0);
    setExpanded(false);
    setJumpRequest(null);
    setSelectedSessionId(null);
    setSearchDraft("");
    setSearchQuery("");
    setSearchPage(0);
  }, [clientId, windowId]);

  const chatRecordQuery = useQuery({
    queryKey: [
      "agent-record",
      "chat",
      clientId,
      windowId,
      chatRoleFilter,
      selectedSessionId,
      chatPage,
      AGENT_RECORD_CHAT_PAGE_SIZE
    ],
    queryFn: () => fetchAgentRecordChat(
      clientId as string,
      windowId as string,
      AGENT_RECORD_CHAT_PAGE_SIZE,
      chatPage * AGENT_RECORD_CHAT_PAGE_SIZE,
      chatRoleFilter,
      expanded ? selectedSessionId : null
    ),
    enabled: enabled && clientId !== null && windowId !== null && mode === "chat",
    placeholderData: keepPreviousData,
    refetchInterval: 10000
  });
  const detailRecordQuery = useQuery({
    queryKey: ["agent-record", "detail", clientId, windowId, selectedSessionId, detailPage, AGENT_RECORD_DETAIL_PAGE_SIZE],
    queryFn: () => fetchAgentRecordDetail(
      clientId as string,
      windowId as string,
      AGENT_RECORD_DETAIL_PAGE_SIZE,
      detailPage * AGENT_RECORD_DETAIL_PAGE_SIZE,
      expanded ? selectedSessionId : null
    ),
    enabled:
      enabled
      && clientId !== null
      && windowId !== null
      && (mode === "detail" || expanded),
    placeholderData: keepPreviousData,
    refetchInterval: 10000
  });
  const activeQuery = mode === "chat" ? chatRecordQuery : detailRecordQuery;
  const searchRecordQuery = useQuery({
    queryKey: ["agent-record", "search", clientId, windowId, searchQuery, searchPage, AGENT_RECORD_SEARCH_PAGE_SIZE],
    queryFn: () => searchWindowAgentRecord(
      clientId as string,
      windowId as string,
      searchQuery,
      AGENT_RECORD_SEARCH_PAGE_SIZE,
      searchPage * AGENT_RECORD_SEARCH_PAGE_SIZE
    ),
    enabled: enabled && clientId !== null && windowId !== null && searchQuery.length > 0,
    placeholderData: keepPreviousData
  });

  const changeMode = useCallback((nextMode: AgentRecordDisplayMode) => {
    setMode(nextMode);
    if (nextMode === "chat") setChatPage(0);
    else setDetailPage(0);
  }, []);
  const changeChatRoleFilter = useCallback((nextRole: AgentChatRoleFilter) => {
    setChatRoleFilter(nextRole);
    setChatPage(0);
  }, []);
  const resetPages = useCallback(() => {
    setChatPage(0);
    setDetailPage(0);
  }, []);
  const pageFromOffset = (offset: number | undefined, pageSize: number): number => {
    if (offset === undefined || offset < 0) {
      return 0;
    }
    return Math.floor(offset / pageSize);
  };
  const changeSelectedSessionId = useCallback((sessionId: string | null, pageOffset?: AgentRecordPageOffset) => {
    setSelectedSessionId(sessionId);
    setChatPage(pageFromOffset(pageOffset?.chatOffset, AGENT_RECORD_CHAT_PAGE_SIZE));
    setDetailPage(pageFromOffset(pageOffset?.detailOffset, AGENT_RECORD_DETAIL_PAGE_SIZE));
  }, []);
  const previousPage = useCallback(() => {
    if (mode === "chat") setChatPage((page) => Math.max(0, page - 1));
    else setDetailPage((page) => Math.max(0, page - 1));
  }, [mode]);
  const nextPage = useCallback(() => {
    if (mode === "chat") setChatPage((page) => page + 1);
    else setDetailPage((page) => page + 1);
  }, [mode]);
  const submitSearch = useCallback((query: string) => {
    const trimmed = query.trim();
    setSearchDraft(query);
    setSearchQuery(trimmed);
    setSearchPage(0);
  }, []);
  const clearSearch = useCallback(() => {
    setSearchDraft("");
    setSearchQuery("");
    setSearchPage(0);
  }, []);
  const previousSearchPage = useCallback(() => {
    setSearchPage((page) => Math.max(0, page - 1));
  }, []);
  const nextSearchPage = useCallback(() => {
    setSearchPage((page) => page + 1);
  }, []);

  return useMemo(() => ({
    mode,
    setMode: changeMode,
    chatRoleFilter,
    setChatRoleFilter: changeChatRoleFilter,
    chatRecord: chatRecordQuery.data ?? null,
    detailRecord: detailRecordQuery.data ?? null,
    sessions: detailRecordQuery.data?.sessions ?? [],
    isLoading: activeQuery.isLoading,
    isError: activeQuery.isError,
    isFetching: activeQuery.isFetching,
    expanded,
    setExpanded,
    jumpRequest,
    setJumpRequest,
    selectedSessionId,
    setSelectedSessionId: changeSelectedSessionId,
    searchDraft,
    setSearchDraft,
    searchQuery,
    searchRecord: searchRecordQuery.data ?? null,
    searchIsLoading: searchRecordQuery.isLoading,
    searchIsError: searchRecordQuery.isError,
    searchIsFetching: searchRecordQuery.isFetching,
    submitSearch,
    clearSearch,
    previousSearchPage,
    nextSearchPage,
    resetPages,
    previousPage,
    nextPage
  }), [
    activeQuery.isError,
    activeQuery.isFetching,
    activeQuery.isLoading,
    changeChatRoleFilter,
    changeMode,
    chatRecordQuery.data,
    chatRoleFilter,
    detailRecordQuery.data,
    expanded,
    jumpRequest,
    mode,
    nextPage,
    nextSearchPage,
    previousPage,
    previousSearchPage,
    changeSelectedSessionId,
    clearSearch,
    resetPages,
    searchDraft,
    searchQuery,
    searchRecordQuery.data,
    searchRecordQuery.isError,
    searchRecordQuery.isFetching,
    searchRecordQuery.isLoading,
    selectedSessionId,
    submitSearch
  ]);
}
