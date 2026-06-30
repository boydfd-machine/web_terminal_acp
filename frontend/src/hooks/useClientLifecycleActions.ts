import { useMutation, type QueryClient } from "@tanstack/react-query";

import { buildRegistrationScriptFromRuntime } from "../clientRegistrationScript";
import { useI18n } from "../i18n";
import { writeClipboardText } from "../terminalClipboard";
import {
  bootstrapClient,
  createClientRegistrationKey,
  updateClient,
} from "../api";
import type { AddClientMode } from "../appTypes";
import type { BootstrapClientInput, Client } from "../types";

type UseClientLifecycleActionsArgs = {
  queryClient: QueryClient;
  setAddClientInitialMode: (mode: AddClientMode) => void;
  setAddClientModalOpen: (open: boolean) => void;
  setBootstrapFailed: (failed: boolean) => void;
  setUpdateFailed: (failed: boolean) => void;
  setUpdateMessage: (message: string | null) => void;
};

export function useClientLifecycleActions({
  queryClient,
  setAddClientInitialMode,
  setAddClientModalOpen,
  setBootstrapFailed,
  setUpdateFailed,
  setUpdateMessage,
}: UseClientLifecycleActionsArgs) {
  const { t } = useI18n();
  const registrationKeyMutation = useMutation({
    mutationFn: (label?: string | null) => createClientRegistrationKey(label),
  });

  const bootstrapMutation = useMutation({
    mutationFn: bootstrapClient,
    onMutate: () => {
      setBootstrapFailed(false);
    },
    onSuccess: () => {
      setAddClientModalOpen(false);
      queryClient.invalidateQueries({ queryKey: ["clients"] });
    },
    onError: () => {
      setBootstrapFailed(true);
    },
    onSettled: () => {
      bootstrapMutation.reset();
    },
  });

  const updateMutation = useMutation({
    mutationFn: updateClient,
    onMutate: () => {
      setUpdateFailed(false);
      setUpdateMessage(null);
    },
    onSuccess: (result) => {
      setUpdateMessage(`Client update started (${result.method}).`);
      queryClient.invalidateQueries({ queryKey: ["clients"] });
    },
    onError: () => {
      setUpdateFailed(true);
    },
  });

  const reregisterClientMutation = useMutation({
    mutationFn: async (client: Client) => {
      const keyResult = await createClientRegistrationKey(client.name);
      const script = buildRegistrationScriptFromRuntime({
        registrationKey: keyResult.key,
        clientName: client.name,
      });
      await writeClipboardText(script, true);
      return client;
    },
    onMutate: () => {
      setUpdateFailed(false);
      setUpdateMessage(null);
    },
    onSuccess: (client) => {
      setUpdateMessage(t("client.reregisterScriptCopied", { name: client.name }));
    },
    onError: () => {
      setUpdateMessage(t("client.reregisterScriptFailed"));
    },
  });

  const submitBootstrap = (payload: BootstrapClientInput) => {
    bootstrapMutation.mutate(payload);
  };

  const openAddClientModal = (mode: AddClientMode) => {
    setAddClientInitialMode(mode);
    setBootstrapFailed(false);
    setAddClientModalOpen(true);
  };

  const closeAddClientModal = () => {
    setAddClientModalOpen(false);
    setBootstrapFailed(false);
    bootstrapMutation.reset();
  };

  return {
    bootstrapMutation,
    closeAddClientModal,
    openAddClientModal,
    registrationKeyMutation,
    reregisterClientMutation,
    submitBootstrap,
    updateMutation,
  };
}
