import type { AgentModelSelection } from "./types";

export const CURSOR_OFFICIAL_MODEL_PRESET_ID = "cursor-official";

export type CursorOfficialModel = {
  id: string;
  label: string;
};

export type CursorOfficialModelList = {
  models: CursorOfficialModel[];
};

export function isCursorOfficialModelSelection(
  selection: AgentModelSelection | null | undefined
): selection is AgentModelSelection {
  return selection?.preset_id === CURSOR_OFFICIAL_MODEL_PRESET_ID;
}

export function cursorOfficialModelSelection(model: string): AgentModelSelection {
  return {
    preset_id: CURSOR_OFFICIAL_MODEL_PRESET_ID,
    model
  };
}

export function cursorOfficialModelValue(selection: AgentModelSelection | null): string {
  return isCursorOfficialModelSelection(selection) ? selection.model ?? "" : "";
}
