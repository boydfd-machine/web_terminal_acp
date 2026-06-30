import type { UseMutationResult } from "@tanstack/react-query";

import { useAppPrompt } from "../components/AppPromptProvider";
import { useI18n } from "../i18n";
import { pickWindowAfterDelete } from "../terminalTreeSelection";
import type { Client, TreeFolder } from "../types";

type DeleteClientMutation = UseMutationResult<unknown, Error, { clientId: string }, unknown>;
type DeleteWindowMutation = UseMutationResult<
  unknown,
  Error,
  { clientId: string; windowId: string; nextWindowId: string | null },
  unknown
>;

type UseTerminalDeleteActionsArgs = {
  deleteClientMutation: DeleteClientMutation;
  deleteMutation: DeleteWindowMutation;
  selectedClientId: string | null;
  selectedWindowId: string | null;
  selectedWindowTitle: string | null;
  treeFolders: TreeFolder[] | undefined;
  setTerminalControlsOpen: (open: boolean) => void;
  setUpdateFailed: (failed: boolean) => void;
  setUpdateMessage: (message: string | null) => void;
};

export function useTerminalDeleteActions({
  deleteClientMutation,
  deleteMutation,
  selectedClientId,
  selectedWindowId,
  selectedWindowTitle,
  treeFolders,
  setTerminalControlsOpen,
  setUpdateFailed,
  setUpdateMessage,
}: UseTerminalDeleteActionsArgs) {
  const { t } = useI18n();
  const { confirm } = useAppPrompt();

  const requestDeleteClient = async (client: Client) => {
    if (client.runtime !== "remote" || deleteClientMutation.isPending) {
      return;
    }

    if (!(await confirm({
      title: t("client.deleteConfirmTitle"),
      message: t("client.deleteConfirm", { name: client.name }),
      confirmLabel: t("client.deleteConfirmSubmit"),
      tone: "danger"
    }))) {
      return;
    }

    setUpdateFailed(false);
    setUpdateMessage(null);
    deleteClientMutation.mutate({ clientId: client.id });
  };

  const requestDeleteWindow = async (windowId: string, title: string) => {
    if (selectedClientId === null || deleteMutation.isPending) {
      return;
    }

    if (!(await confirm({
      title: t("terminal.deleteConfirmTitle"),
      message: t("terminal.deleteConfirm", { title }),
      confirmLabel: t("terminal.deleteConfirmSubmit"),
      tone: "danger"
    }))) {
      return;
    }

    setTerminalControlsOpen(false);
    deleteMutation.mutate({
      clientId: selectedClientId,
      windowId,
      nextWindowId: pickWindowAfterDelete(treeFolders, windowId),
    });
  };

  const confirmDeleteTerminal = () => {
    if (selectedWindowId === null) {
      return;
    }

    requestDeleteWindow(selectedWindowId, selectedWindowTitle ?? "this terminal");
  };

  return {
    confirmDeleteTerminal,
    requestDeleteClient,
    requestDeleteWindow,
  };
}
