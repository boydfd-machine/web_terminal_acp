import { useCallback, useEffect, useState, type MutableRefObject } from "react";
import { useMutation, useQuery, type QueryClient } from "@tanstack/react-query";

import { fetchCustomQuickKeys, updateCustomQuickKeys } from "../api";
import type { TerminalPaneHandle } from "../components/TerminalPane";
import {
  clearLegacyCustomQuickKeys,
  decodeQuickKeyInput,
  normalizeCustomQuickKeys,
  readLegacyCustomQuickKeys,
  type CustomQuickKey,
} from "../terminalQuickKeys";

type UseCustomQuickKeysArgs = {
  queryClient: QueryClient;
  terminalPaneRef: MutableRefObject<TerminalPaneHandle | null>;
};

export function useCustomQuickKeys({
  queryClient,
  terminalPaneRef,
}: UseCustomQuickKeysArgs) {
  const [customQuickKeys, setCustomQuickKeys] = useState<CustomQuickKey[]>([]);
  const customQuickKeysQuery = useQuery({
    queryKey: ["custom-quick-keys"],
    queryFn: fetchCustomQuickKeys,
  });
  const {
    mutate: mutateCustomQuickKeys,
    isPending: customQuickKeysUpdatePending,
  } = useMutation({
    mutationFn: updateCustomQuickKeys,
    onSuccess: (result) => {
      setCustomQuickKeys(normalizeCustomQuickKeys(result.quick_keys));
      queryClient.setQueryData(["custom-quick-keys"], result);
      clearLegacyCustomQuickKeys();
    },
  });

  useEffect(() => {
    if (!customQuickKeysQuery.isSuccess) {
      return;
    }

    const serverQuickKeys = normalizeCustomQuickKeys(customQuickKeysQuery.data.quick_keys);
    if (customQuickKeysUpdatePending) {
      return;
    }
    setCustomQuickKeys(serverQuickKeys);
    if (serverQuickKeys.length > 0) {
      return;
    }

    const legacyQuickKeys = readLegacyCustomQuickKeys();
    if (legacyQuickKeys.length === 0) {
      return;
    }
    setCustomQuickKeys(legacyQuickKeys);
    mutateCustomQuickKeys(legacyQuickKeys);
  }, [
    customQuickKeysQuery.data,
    customQuickKeysQuery.isSuccess,
    customQuickKeysUpdatePending,
    mutateCustomQuickKeys,
  ]);

  const handleCustomQuickKeysChange = useCallback((quickKeys: CustomQuickKey[]) => {
    const normalizedQuickKeys = normalizeCustomQuickKeys(quickKeys);
    setCustomQuickKeys(normalizedQuickKeys);
    mutateCustomQuickKeys(normalizedQuickKeys);
  }, [mutateCustomQuickKeys]);

  const submitCustomQuickKey = useCallback((quickKey: CustomQuickKey) => {
    return terminalPaneRef.current?.submitQuickInput(decodeQuickKeyInput(quickKey.input)) ?? false;
  }, [terminalPaneRef]);

  return {
    customQuickKeys,
    handleCustomQuickKeysChange,
    submitCustomQuickKey,
  };
}
