import type { KeyboardEvent as ReactKeyboardEvent } from "react";

import { normalizeApiBaseInput, readApiBase } from "../../apiBase";
import { supportedAppLocales, useI18n, type AppLocale } from "../../i18n";
import {
  clampArtifactTerminalRetentionSeconds,
  desktopNotificationsSupported,
  MAX_ARTIFACT_TERMINAL_RETENTION_SECONDS,
  MIN_ARTIFACT_TERMINAL_RETENTION_SECONDS,
  type SummaryOutputLanguage,
  type TerminalGroupingMode,
  type ThemeSkinId
} from "../../userPreferences";
import { effectiveKeyboardShortcut, keyboardShortcutLabel, type KeyboardShortcut, type KeyboardShortcutId } from "../../keyboardShortcuts";
import { quickKeyToken, TERMINAL_SPECIAL_KEYS, type CustomQuickKey } from "../../terminalQuickKeys";
import { THEME_SKINS } from "../../themeSkins";
import { ShortcutRecorder } from "../../components/ShortcutRecorder";
import {
  shortcutConflictLabel,
  shortcutTargetKey,
  type SettingsDraft,
  type ShortcutBindingTarget
} from "./settingsModalData";

type ChangeDraft = (patch: Partial<SettingsDraft>) => void;

type GeneralSettingsPageProps = {
  apiBaseError: string | null;
  draft: SettingsDraft;
  changeDraft: ChangeDraft;
  saveSettings: () => Promise<void>;
  setApiBaseError: (value: string | null) => void;
};

export function GeneralSettingsPage({ apiBaseError, draft, changeDraft, saveSettings, setApiBaseError }: GeneralSettingsPageProps) {
  const { t } = useI18n();

  return (
    <section className="settings-general-page">
      <label className="settings-field">
        <span>{t("settings.general.backendAddress")}</span>
        <input
          value={draft.apiBase}
          onChange={(event) => {
            changeDraft({ apiBase: event.target.value });
            setApiBaseError(null);
          }}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              event.preventDefault();
              void saveSettings();
            }
          }}
          placeholder={readApiBase()}
        />
      </label>
      <div className="settings-actions">
        <button type="button" onClick={() => changeDraft({ apiBase: "" })}>{t("settings.general.defaultBackend")}</button>
      </div>
      {apiBaseError && <p className="error settings-error" role="alert">{apiBaseError}</p>}
      <label className="settings-field">
        <span>{t("app.language")}</span>
        <select value={draft.appLocale} onChange={(event) => changeDraft({ appLocale: event.target.value as AppLocale })}>
          {supportedAppLocales().map((locale) => (
            <option key={locale} value={locale}>
              {locale === "zh-CN" ? t("app.language.zh") : t("app.language.en")}
            </option>
          ))}
        </select>
      </label>
      <label className="settings-field">
        <span>{t("settings.general.summaryLanguage")}</span>
        <select value={draft.summaryOutputLanguage} onChange={(event) => changeDraft({ summaryOutputLanguage: event.target.value as SummaryOutputLanguage })}>
          <option value="中文">{t("settings.general.summaryLanguage.zh")}</option>
          <option value="English">{t("settings.general.summaryLanguage.en")}</option>
        </select>
      </label>
      <label className="settings-field">
        <span>{t("settings.general.terminalGrouping")}</span>
        <select value={draft.terminalGroupingMode} onChange={(event) => changeDraft({ terminalGroupingMode: event.target.value as TerminalGroupingMode })}>
          <option value="project-topic">{t("settings.general.group.projectTopic")}</option>
          <option value="topic">{t("settings.general.group.topic")}</option>
          <option value="time-topic">{t("settings.general.group.timeTopic")}</option>
          <option value="project-time-topic">{t("settings.general.group.projectTimeTopic")}</option>
        </select>
      </label>
      <label className="settings-field">
        <span>{t("settings.general.artifactRetention")}</span>
        <input
          type="number"
          min={MIN_ARTIFACT_TERMINAL_RETENTION_SECONDS}
          max={MAX_ARTIFACT_TERMINAL_RETENTION_SECONDS}
          step={30}
          value={draft.artifactTerminalRetentionSeconds}
          onChange={(event) => changeDraft({ artifactTerminalRetentionSeconds: clampArtifactTerminalRetentionSeconds(Number(event.target.value)) })}
        />
      </label>
      {desktopNotificationsSupported() && (
        <label className="settings-field settings-field-checkbox">
          <span>{t("settings.general.desktopNotifications")}</span>
          <input type="checkbox" checked={draft.desktopNotificationsEnabled} onChange={(event) => changeDraft({ desktopNotificationsEnabled: event.target.checked })} />
        </label>
      )}
      <p className="muted settings-hint">
        {t("settings.general.shortcutHint", { shortcut: keyboardShortcutLabel(effectiveKeyboardShortcut("settings", draft.keyboardShortcutBindings), t) })}
      </p>
    </section>
  );
}

export function ThemeSettingsPage({ draft, changeDraft }: { draft: SettingsDraft; changeDraft: ChangeDraft }) {
  const { t } = useI18n();

  return (
    <section className="settings-theme-page">
      <label className="settings-field">
        <span>{t("settings.theme.currentSkin")}</span>
        <select value={draft.themeSkin} onChange={(event) => changeDraft({ themeSkin: event.target.value as ThemeSkinId })}>
          {THEME_SKINS.map((skin) => <option key={skin.id} value={skin.id}>{skin.label}</option>)}
        </select>
      </label>
      <div className="settings-skin-preview-grid" aria-label={t("settings.theme.preview")}>
        {THEME_SKINS.map((skin) => (
          <button
            key={skin.id}
            type="button"
            className={["settings-skin-preview", skin.cssClass, skin.id === draft.themeSkin ? "selected" : ""].filter(Boolean).join(" ")}
            aria-pressed={skin.id === draft.themeSkin}
            onClick={() => changeDraft({ themeSkin: skin.id })}
          >
            <span className="settings-skin-preview-header"><strong>{skin.label}</strong><span>{skin.source}</span></span>
            <span className="settings-skin-preview-swatch" aria-hidden="true"><i /><i /><i /></span>
            <span className="settings-skin-preview-summary">{t(skin.summaryKey)}</span>
          </button>
        ))}
      </div>
    </section>
  );
}

type ShortcutsSettingsPageProps = {
  bindDefaultShortcut: (id: KeyboardShortcutId) => void;
  bindShortcut: (target: ShortcutBindingTarget, shortcut: KeyboardShortcut | null) => void;
  captureShortcut: (target: ShortcutBindingTarget, event: ReactKeyboardEvent<HTMLButtonElement>) => void;
  draft: SettingsDraft;
  recordingShortcutTarget: ShortcutBindingTarget | null;
  resetAllBuiltInShortcuts: () => void;
  setRecordingShortcutTarget: (target: ShortcutBindingTarget | null) => void;
  shortcutRows: Array<{ target: ShortcutBindingTarget; label: string; shortcut: KeyboardShortcut | null; defaultShortcut?: KeyboardShortcut }>;
};

export function ShortcutsSettingsPage({ bindDefaultShortcut, bindShortcut, captureShortcut, draft, recordingShortcutTarget, resetAllBuiltInShortcuts, setRecordingShortcutTarget, shortcutRows }: ShortcutsSettingsPageProps) {
  const { t } = useI18n();

  return (
    <section className="shortcut-binding-page">
      <div className="shortcut-binding-toolbar"><button type="button" onClick={resetAllBuiltInShortcuts}>{t("settings.shortcuts.restoreDefaults")}</button></div>
      <div className="shortcut-binding-list">
        {shortcutRows.map((row) => {
          const builtInShortcutId = row.target.type === "builtin" ? row.target.id : null;
          return (
            <article key={shortcutTargetKey(row.target)} className="shortcut-binding-item">
              <div className="shortcut-binding-label">
                <strong>{row.label}</strong>
                {builtInShortcutId !== null && <span>{t("settings.shortcuts.default", { shortcut: keyboardShortcutLabel(row.defaultShortcut ?? null, t) })}</span>}
              </div>
              <ShortcutRecorder
                label={row.label}
                shortcut={row.shortcut}
                target={row.target}
                recordingTarget={recordingShortcutTarget}
                conflictLabel={shortcutConflictLabel(row.shortcut, row.target, draft.keyboardShortcutBindings, draft.customQuickKeys, t)}
                onStartRecording={setRecordingShortcutTarget}
                onCapture={captureShortcut}
                onClear={(target) => bindShortcut(target, null)}
              />
              {builtInShortcutId !== null ? <button type="button" onClick={() => bindDefaultShortcut(builtInShortcutId)}>{t("settings.shortcuts.defaultButton")}</button> : null}
            </article>
          );
        })}
      </div>
    </section>
  );
}

type QuickKeysSettingsPageProps = {
  addQuickKey: () => void;
  appendSpecialKeyToDraft: (token: string) => void;
  bindShortcut: (target: ShortcutBindingTarget, shortcut: KeyboardShortcut | null) => void;
  captureShortcut: (target: ShortcutBindingTarget, event: ReactKeyboardEvent<HTMLButtonElement>) => void;
  draft: SettingsDraft;
  quickKeyDraft: CustomQuickKey;
  quickKeyDraftValid: boolean;
  recordingShortcutTarget: ShortcutBindingTarget | null;
  removeQuickKey: (id: string) => void;
  resetQuickKeyDraft: () => void;
  setRecordingShortcutTarget: (target: ShortcutBindingTarget | null) => void;
  updateQuickKey: (id: string, patch: Partial<CustomQuickKey>) => void;
  updateQuickKeyDraft: (patch: Partial<CustomQuickKey>) => void;
};

export function QuickKeysSettingsPage({ addQuickKey, appendSpecialKeyToDraft, bindShortcut, captureShortcut, draft, quickKeyDraft, quickKeyDraftValid, recordingShortcutTarget, removeQuickKey, resetQuickKeyDraft, setRecordingShortcutTarget, updateQuickKey, updateQuickKeyDraft }: QuickKeysSettingsPageProps) {
  const { t } = useI18n();

  return (
    <section className="quick-key-page">
      <div className="quick-key-editor">
        <div className="quick-key-editor-grid">
          <label className="settings-field"><span>{t("settings.quickKeys.name")}</span><input value={quickKeyDraft.label} onChange={(event) => updateQuickKeyDraft({ label: event.target.value })} placeholder={t("settings.quickKeys.namePlaceholder")} /></label>
          <label className="settings-field quick-key-input-field"><span>{t("settings.quickKeys.input")}</span><textarea value={quickKeyDraft.input} onChange={(event) => updateQuickKeyDraft({ input: event.target.value })} placeholder={t("settings.quickKeys.inputPlaceholder")} rows={3} /></label>
        </div>
        <div className="quick-key-draft-shortcut">
          <span>{t("settings.quickKeys.shortcut")}</span>
          <ShortcutRecorder label={t("settings.quickKeys.newShortcut")} shortcut={quickKeyDraft.shortcut ?? null} target={{ type: "quick-key-draft" }} recordingTarget={recordingShortcutTarget} conflictLabel={shortcutConflictLabel(quickKeyDraft.shortcut ?? null, { type: "quick-key-draft" }, draft.keyboardShortcutBindings, draft.customQuickKeys, t)} onStartRecording={setRecordingShortcutTarget} onCapture={captureShortcut} onClear={(target) => bindShortcut(target, null)} />
        </div>
        <div className="quick-key-special-picker" aria-label={t("settings.quickKeys.specialKeys")}>
          {TERMINAL_SPECIAL_KEYS.map((key) => <button key={key.token} type="button" onClick={() => appendSpecialKeyToDraft(key.token)}>{key.label}</button>)}
        </div>
        <div className="settings-actions"><button type="button" disabled={!quickKeyDraftValid} onClick={addQuickKey}>{t("settings.quickKeys.add")}</button><button type="button" onClick={resetQuickKeyDraft}>{t("settings.quickKeys.clear")}</button></div>
      </div>
      <div className="quick-key-list-header"><h3>{t("settings.quickKeys.existing")}</h3><span>{draft.customQuickKeys.length}</span></div>
      {draft.customQuickKeys.length === 0 ? <p className="muted quick-key-empty-state">{t("settings.quickKeys.empty")}</p> : (
        <div className="quick-key-settings-list">
          {draft.customQuickKeys.map((quickKey) => (
            <article key={quickKey.id} className="quick-key-settings-item">
              <label className="settings-field"><span>{t("settings.quickKeys.name")}</span><input value={quickKey.label} onChange={(event) => updateQuickKey(quickKey.id, { label: event.target.value })} /></label>
              <label className="settings-field"><span>{t("settings.quickKeys.input")}</span><textarea value={quickKey.input} rows={2} onChange={(event) => updateQuickKey(quickKey.id, { input: event.target.value })} /></label>
              <div className="quick-key-item-shortcut">
                <span>{t("settings.quickKeys.shortcut")}</span>
                <ShortcutRecorder label={quickKey.label} shortcut={quickKey.shortcut ?? null} target={{ type: "quick-key", id: quickKey.id }} recordingTarget={recordingShortcutTarget} conflictLabel={shortcutConflictLabel(quickKey.shortcut ?? null, { type: "quick-key", id: quickKey.id }, draft.keyboardShortcutBindings, draft.customQuickKeys, t)} onStartRecording={setRecordingShortcutTarget} onCapture={captureShortcut} onClear={(target) => bindShortcut(target, null)} />
              </div>
              <button type="button" onClick={() => removeQuickKey(quickKey.id)}>{t("settings.quickKeys.delete")}</button>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

export function AccountSettingsPage({ authEnabled, onboardingEnabled, onLogout, onStartOnboarding }: { authEnabled: boolean; onboardingEnabled: boolean; onLogout: () => void; onStartOnboarding: () => void }) {
  const { t } = useI18n();

  return (
    <section className="settings-account-page">
      {onboardingEnabled && <button type="button" className="settings-nav-row" onClick={onStartOnboarding}><span>{t("settings.account.onboarding")}</span><strong>{t("settings.account.start")}</strong></button>}
      {authEnabled && <div className="settings-actions"><button type="button" onClick={onLogout}>{t("settings.account.logout")}</button></div>}
    </section>
  );
}
