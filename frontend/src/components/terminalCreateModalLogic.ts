import { isAgentLaunchKind } from "../agentLaunch";
import type { AgentLaunchMode } from "../agentLaunch";
import type { AgentModelSelectionSettings } from "../userPreferences";
import type { AgentConfig, AgentConfigSelection, AgentLaunchKind, AgentModelSelection } from "../types";

export function selectionForConfig(configAgent: AgentLaunchKind, current: AgentConfigSelection | null) {
  if (current !== null && current.agent === configAgent) {
    return current;
  }
  return null;
}

export function agentConfigSelectionsEqual(
  left: AgentConfigSelection | null,
  right: AgentConfigSelection | null
): boolean {
  if (left === right) {
    return true;
  }
  if (left === null || right === null || left.agent !== right.agent || left.sections.length !== right.sections.length) {
    return false;
  }
  return left.sections.every((leftSection, sectionIndex) => {
    const rightSection = right.sections[sectionIndex];
    return rightSection !== undefined
      && leftSection.id === rightSection.id
      && leftSection.items.length === rightSection.items.length
      && leftSection.items.every((leftItem, itemIndex) => {
        const rightItem = rightSection.items[itemIndex];
        return rightItem !== undefined
          && leftItem.id === rightItem.id
          && leftItem.enabled === rightItem.enabled;
      });
  });
}

export function mergeConfigWithSystemDefaults(
  config: AgentConfig | null,
  systemConfig: AgentConfig | null
): AgentConfig | null {
  if (config === null) {
    return null;
  }
  if (systemConfig === null) {
    return config;
  }

  const configSections = Array.isArray(config.sections) ? config.sections : [];
  const systemSections = new Map(
    (Array.isArray(systemConfig.sections) ? systemConfig.sections : [])
      .map((section) => [section.id, section])
  );
  return {
    ...config,
    sections: configSections.map((section) => {
      if (section.id !== "skills" && section.id !== "mcp") {
        return section;
      }
      const systemSection = systemSections.get(section.id);
      if (systemSection === undefined) {
        return section;
      }
      const itemIds = new Set(section.items.map((item) => item.id));
      return {
        ...section,
        items: [
          ...section.items,
          ...systemSection.items.filter((item) => !itemIds.has(item.id))
        ]
      };
    })
  };
}

export function defaultModelSelection(
  agent: AgentLaunchMode,
  settings: AgentModelSelectionSettings
): AgentModelSelection | null {
  return isAgentLaunchKind(agent) ? settings[agent] ?? null : null;
}
