import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { UiIcon } from "../../components/UiIcon";
import { useAppPrompt } from "../../components/AppPromptProvider";
import { useOverlayFocus } from "../../components/useOverlayFocus";
import { useI18n } from "../../i18n";
import { AgentSettingsPage } from "./AgentSettingsPage";
import { ProjectTodoTypeManager } from "../../components/ProjectTodoTypeManager";
import { SettingsArtifactPluginsPage } from "./SettingsArtifactPluginsPage";
import { AccountSettingsPage, GeneralSettingsPage, QuickKeysSettingsPage, ShortcutsSettingsPage, ThemeSettingsPage } from "./SettingsPages";
import { SystemAgentConfigSettings } from "./SystemAgentConfigSettings";
import { SystemModelSettings } from "./SystemModelSettings";
import { useAgentProfilesSettings } from "./useAgentProfilesSettings";
import { useQuickKeysSettings } from "./useQuickKeysSettings";
import { useSettingsDraft } from "./useSettingsDraft";
import { useShortcutBindings } from "./useShortcutBindings";
import {
  SETTINGS_TABS,
  type SettingsModalProps,
  type SettingsTabId,
  type SettingsView
} from "./settingsModalData";

export type { SettingsView };
export { readInitialSettings } from "./useSettingsDraft";

export function SettingsModal({
  isOpen,
  onClose,
  appLocale,
  summaryOutputLanguage,
  terminalGroupingMode,
  terminalTimeRange,
  themeSkin,
  desktopNotificationsEnabled,
  keyboardShortcutBindings,
  customQuickKeys,
  selectedClientId,
  selectedProjectPath = null,
  selectedWindowId = null,
  onAppLocaleChange,
  onSummaryOutputLanguageChange,
  onTerminalGroupingModeChange,
  onThemeSkinChange,
  onDesktopNotificationsEnabledChange,
  onKeyboardShortcutBindingsChange,
  onCustomQuickKeysChange,
  onAppPreferencesSave,
  authEnabled,
  initialView = "general",
  onboardingEnabled,
  onStartOnboarding,
  onLogout
}: SettingsModalProps) {
  const { t } = useI18n();
  const { confirm } = useAppPrompt();
  const [view, setView] = useState<SettingsTabId>("general");
  const [artifactPreviewModalOpen, setArtifactPreviewModalOpen] = useState(false);
  const panelRef = useRef<HTMLDivElement | null>(null);
  const wasOpenRef = useRef(false);
  const {
    apiBaseError,
    changeDraft,
    draft,
    hasUnsavedChanges,
    saveSettings,
    saveStatus,
    setApiBaseError,
    updateAgentCommand,
    updateAgentModelSelection,
    updateArtifactModelSelection
  } = useSettingsDraft({
    isOpen,
    appLocale,
    summaryOutputLanguage,
    terminalGroupingMode,
    terminalTimeRange,
    themeSkin,
    desktopNotificationsEnabled,
    keyboardShortcutBindings,
    customQuickKeys,
    onAppLocaleChange,
    onSummaryOutputLanguageChange,
    onTerminalGroupingModeChange,
    onThemeSkinChange,
    onDesktopNotificationsEnabledChange,
    onKeyboardShortcutBindingsChange,
    onCustomQuickKeysChange,
    onAppPreferencesSave
  });
  const {
    addQuickKey,
    appendSpecialKeyToDraft,
    quickKeyDraft,
    quickKeyDraftValid,
    removeQuickKey,
    resetQuickKeyDraft,
    updateQuickKey,
    updateQuickKeyDraft
  } = useQuickKeysSettings({
    changeDraft,
    customQuickKeys: draft.customQuickKeys
  });
  const {
    bindDefaultShortcut,
    bindShortcut,
    captureShortcut,
    recordingShortcutTarget,
    resetAllBuiltInShortcuts,
    setRecordingShortcutTarget,
    shortcutRows
  } = useShortcutBindings({
    changeDraft,
    customQuickKeys: draft.customQuickKeys,
    keyboardShortcutBindings: draft.keyboardShortcutBindings,
    updateQuickKey,
    updateQuickKeyDraft
  });
  const canShowAccountTab = authEnabled || onboardingEnabled;
  const visibleTabs = useMemo(
    () => SETTINGS_TABS.filter((tab) => tab.id !== "account" || canShowAccountTab),
    [canShowAccountTab]
  );
  const agentProfileSettings = useAgentProfilesSettings({ isOpen, selectedClientId, view });

  useEffect(() => {
    if (!isOpen) {
      wasOpenRef.current = false;
      setArtifactPreviewModalOpen(false);
      return;
    }
    if (wasOpenRef.current) {
      return;
    }

    wasOpenRef.current = true;
    setArtifactPreviewModalOpen(false);
    setRecordingShortcutTarget(null);
    setView(initialView);
  }, [initialView, isOpen, setRecordingShortcutTarget]);

  useEffect(() => {
    if (view !== "artifacts") {
      setArtifactPreviewModalOpen(false);
    }
  }, [view]);

  const requestClose = useCallback(async () => {
    if (artifactPreviewModalOpen) {
      setArtifactPreviewModalOpen(false);
      return;
    }

    if (recordingShortcutTarget !== null) {
      setRecordingShortcutTarget(null);
      return;
    }

    if (hasUnsavedChanges && !(await confirm({
      title: t("app.settings.unsavedTitle"),
      message: t("app.settings.unsavedConfirm"),
      confirmLabel: t("app.settings.unsavedDiscard"),
      tone: "danger"
    }))) {
      return;
    }
    onClose();
  }, [artifactPreviewModalOpen, confirm, hasUnsavedChanges, onClose, recordingShortcutTarget, setRecordingShortcutTarget, t]);

  useOverlayFocus({
    isOpen,
    ref: panelRef,
    onEscape: requestClose
  });

  if (!isOpen) {
    return null;
  }

  return (
    <div
      className="settings-modal-backdrop"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) {
          requestClose();
        }
      }}
    >
      <div
        ref={panelRef}
        aria-modal="true"
        className={[
          "settings-modal",
          "settings-modal-wide",
          view === "card-types" || view === "system-skills" || view === "system-plugins" || view === "system-mcp" || view === "system-models" || view === "artifacts"
            ? "settings-modal-system-config"
            : ""
        ].filter(Boolean).join(" ")}
        data-onboarding-id="settings-modal"
        role="dialog"
        aria-label={t("app.settings")}
      >
        <div className="settings-modal-header">
          <div className="settings-modal-title">
            <h2>{t("app.settings")}</h2>
            {hasUnsavedChanges && <span className="settings-dirty-badge">{t("app.settings.unsaved")}</span>}
          </div>
          <button
            type="button"
            className="ui-icon-button"
            aria-label={t("app.settings.close")}
            title={t("app.settings.close")}
            onClick={requestClose}
          >
            <UiIcon name="x" />
          </button>
        </div>
        <div className="settings-tabs" role="tablist" aria-label={t("app.settings.tabs")}>
          {visibleTabs.map((tab) => (
            <button
              key={tab.id}
              type="button"
              role="tab"
              aria-selected={view === tab.id}
              className={view === tab.id ? "active" : ""}
              onClick={() => setView(tab.id)}
            >
              {t(tab.labelKey)}
            </button>
          ))}
        </div>

        {view === "general" ? (
          <GeneralSettingsPage
            apiBaseError={apiBaseError}
            draft={draft}
            changeDraft={changeDraft}
            saveSettings={saveSettings}
            setApiBaseError={setApiBaseError}
          />
        ) : view === "theme" ? (
          <ThemeSettingsPage draft={draft} changeDraft={changeDraft} />
        ) : view === "agents" ? (
          <AgentSettingsPage
            agentClients={agentProfileSettings.agentClients}
            selectedClientId={selectedClientId}
            profiles={agentProfileSettings.agentProfiles}
            selectedProfile={agentProfileSettings.selectedAgentProfile}
            profileConfig={agentProfileSettings.profileConfigQuery.data ?? null}
            profileConfigAgentClient={agentProfileSettings.profileConfigAgentClient}
            profileDraftName={agentProfileSettings.profileDraftName}
            profileDraftDescription={agentProfileSettings.profileDraftDescription}
            profileDraftAgentClient={agentProfileSettings.profileDraftAgentClient}
            profileAgentMdDraft={agentProfileSettings.profileAgentMdDraft}
            pendingProfileConfigItem={agentProfileSettings.pendingProfileConfigItem}
            profilesLoading={agentProfileSettings.agentProfilesQuery.isLoading}
            profilesError={agentProfileSettings.agentProfilesQuery.isError}
            configLoading={agentProfileSettings.profileConfigQuery.isLoading}
            configError={agentProfileSettings.profileConfigQuery.isError}
            configFetching={agentProfileSettings.profileConfigQuery.isFetching}
            creatingProfile={agentProfileSettings.createProfileMutation.isPending}
            updatingProfile={agentProfileSettings.updateProfileMutation.isPending}
            deletingProfile={agentProfileSettings.deleteProfileMutation.isPending}
            importingProfile={agentProfileSettings.importProfileMutation.isPending}
            updatingConfig={agentProfileSettings.updateProfileConfigMutation.isPending}
            onSelectProfile={agentProfileSettings.setSelectedAgentProfileId}
            onProfileDraftNameChange={agentProfileSettings.setProfileDraftName}
            onProfileDraftDescriptionChange={agentProfileSettings.setProfileDraftDescription}
            onProfileDraftAgentClientChange={agentProfileSettings.setProfileDraftAgentClient}
            onCreateProfile={agentProfileSettings.createProfile}
            onDeleteProfile={(profile) => agentProfileSettings.deleteProfileMutation.mutate(profile)}
            onImportProfile={agentProfileSettings.importProfile}
            onProfileConfigAgentClientChange={agentProfileSettings.setProfileConfigAgentClient}
            onSaveProfileBasics={agentProfileSettings.saveProfileBasics}
            onAgentMdDraftChange={agentProfileSettings.setProfileAgentMdDraft}
            onSaveAgentMd={agentProfileSettings.saveProfileAgentMd}
            onToggleConfigItem={(sectionId, itemId, enabled) => agentProfileSettings.updateProfileConfigMutation.mutate({ sectionId, itemId, enabled })}
          />
        ) : view === "card-types" ? (
          <SettingsCardTypesPage
            selectedClientId={selectedClientId}
            selectedProjectPath={selectedProjectPath}
          />
        ) : view === "system-skills" || view === "system-plugins" || view === "system-mcp" ? (
          <SystemAgentConfigSettings view={view} />
        ) : view === "system-models" ? (
          <SystemModelSettings
            clientId={selectedClientId}
            agentClients={agentProfileSettings.agentClients}
            agentCommandSettings={draft.agentCommandSettings}
            agentModelSelectionSettings={draft.agentModelSelectionSettings}
            artifactModelSelectionSettings={draft.artifactModelSelectionSettings}
            onAgentCommandChange={updateAgentCommand}
            onAgentModelSelectionChange={updateAgentModelSelection}
            onArtifactModelSelectionChange={updateArtifactModelSelection}
          />
        ) : view === "artifacts" ? (
          <SettingsArtifactPluginsPage
            previewModalOpen={artifactPreviewModalOpen}
            selectedClientId={selectedClientId}
            selectedWindowId={selectedWindowId}
            userPreferredLanguage={draft.summaryOutputLanguage}
            onPreviewModalOpenChange={setArtifactPreviewModalOpen}
          />
        ) : view === "shortcuts" ? (
          <ShortcutsSettingsPage
            bindDefaultShortcut={bindDefaultShortcut}
            bindShortcut={bindShortcut}
            captureShortcut={captureShortcut}
            draft={draft}
            recordingShortcutTarget={recordingShortcutTarget}
            resetAllBuiltInShortcuts={resetAllBuiltInShortcuts}
            setRecordingShortcutTarget={setRecordingShortcutTarget}
            shortcutRows={shortcutRows}
          />
        ) : view === "quick-keys" ? (
          <QuickKeysSettingsPage
            addQuickKey={addQuickKey}
            appendSpecialKeyToDraft={appendSpecialKeyToDraft}
            bindShortcut={bindShortcut}
            captureShortcut={captureShortcut}
            draft={draft}
            quickKeyDraft={quickKeyDraft}
            quickKeyDraftValid={quickKeyDraftValid}
            recordingShortcutTarget={recordingShortcutTarget}
            removeQuickKey={removeQuickKey}
            resetQuickKeyDraft={resetQuickKeyDraft}
            setRecordingShortcutTarget={setRecordingShortcutTarget}
            updateQuickKey={updateQuickKey}
            updateQuickKeyDraft={updateQuickKeyDraft}
          />
        ) : (
          <AccountSettingsPage
            authEnabled={authEnabled}
            onboardingEnabled={onboardingEnabled}
            onLogout={onLogout}
            onStartOnboarding={onStartOnboarding}
          />
        )}
        <div className="settings-save-bar">
          <span className={hasUnsavedChanges ? "settings-save-state dirty" : "settings-save-state"}>
            {apiBaseError ?? saveStatus ?? (hasUnsavedChanges ? t("app.settings.save.unsaved") : t("app.settings.save.clean"))}
          </span>
          <div className="settings-save-actions">
            <button
              type="button"
              className="ui-icon-button"
              aria-label={t("app.settings.save.cancel")}
              title={t("app.settings.save.cancel")}
              onClick={requestClose}
            >
              <UiIcon name="x" />
            </button>
            <button
              type="button"
              className="settings-save-button ui-icon-button"
              disabled={!hasUnsavedChanges}
              aria-label={t("app.settings.save.submit")}
              title={t("app.settings.save.submit")}
              onClick={() => void saveSettings()}
            >
              <UiIcon name="save" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function SettingsCardTypesPage({
  selectedClientId,
  selectedProjectPath
}: {
  selectedClientId: string | null;
  selectedProjectPath: string | null;
}) {
  const { t } = useI18n();

  if (selectedClientId === null) {
    return (
      <section className="settings-card-types-page">
        <p className="muted">{t("app.settings.noClientForCardTypes")}</p>
      </section>
    );
  }

  const projectPath = selectedProjectPath ?? "/";
  return (
    <section className="settings-card-types-page">
      <ProjectTodoTypeManager
        clientId={selectedClientId}
        projectPath={projectPath}
        title={t("settings.cardTypes.title")}
        contextLabel={selectedProjectPath === null ? t("settings.cardTypes.system") : selectedProjectPath}
      />
    </section>
  );
}
