import {
  desktopNotificationsSupported,
  readDesktopNotificationsEnabled,
  readSummaryOutputLanguage,
  readTerminalGroupingMode,
  type SummaryOutputLanguage,
  type TerminalGroupingMode,
  writeDesktopNotificationsEnabled,
  writeSummaryOutputLanguage,
  writeTerminalGroupingMode
} from "../userPreferences";
import { ensureDesktopNotificationPermission } from "../desktopNotifications";
import { readApiBase, readConfiguredApiBase, writeConfiguredApiBase } from "../apiBase";
import { useEffect, useState } from "react";

type SettingsModalProps = {
  isOpen: boolean;
  onClose: () => void;
  summaryOutputLanguage: SummaryOutputLanguage;
  terminalGroupingMode: TerminalGroupingMode;
  desktopNotificationsEnabled: boolean;
  onSummaryOutputLanguageChange: (language: SummaryOutputLanguage) => void;
  onTerminalGroupingModeChange: (mode: TerminalGroupingMode) => void;
  onDesktopNotificationsEnabledChange: (enabled: boolean) => void;
};

export function SettingsModal({
  isOpen,
  onClose,
  summaryOutputLanguage,
  terminalGroupingMode,
  desktopNotificationsEnabled,
  onSummaryOutputLanguageChange,
  onTerminalGroupingModeChange,
  onDesktopNotificationsEnabledChange
}: SettingsModalProps) {
  const [apiBaseDraft, setApiBaseDraft] = useState("");
  const [apiBaseError, setApiBaseError] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen) {
      setApiBaseDraft(readConfiguredApiBase());
      setApiBaseError(null);
    }
  }, [isOpen]);

  if (!isOpen) {
    return null;
  }

  const saveApiBase = (value: string) => {
    try {
      writeConfiguredApiBase(value);
      window.location.reload();
    } catch {
      setApiBaseError("请输入有效的 HTTP/HTTPS 地址");
    }
  };

  return (
    <div
      className="settings-modal-backdrop"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) {
          onClose();
        }
      }}
    >
      <div aria-modal="true" className="settings-modal" role="dialog" aria-label="Settings">
        <div className="settings-modal-header">
          <h2>设置</h2>
          <button type="button" onClick={onClose}>
            关闭
          </button>
        </div>

        <label className="settings-field">
          <span>后端地址</span>
          <input
            value={apiBaseDraft}
            onChange={(event) => {
              setApiBaseDraft(event.target.value);
              setApiBaseError(null);
            }}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                event.preventDefault();
                saveApiBase(apiBaseDraft);
              }
            }}
            placeholder={readApiBase()}
          />
        </label>
        <div className="settings-actions">
          <button type="button" onClick={() => saveApiBase(apiBaseDraft)}>
            保存后端地址
          </button>
          <button
            type="button"
            onClick={() => {
              setApiBaseDraft("");
              saveApiBase("");
            }}
          >
            恢复默认
          </button>
        </div>
        {apiBaseError && (
          <p className="error settings-error" role="alert">
            {apiBaseError}
          </p>
        )}

        <label className="settings-field">
          <span>项目名显示语言</span>
          <select
            value={summaryOutputLanguage}
            onChange={(event) => {
              const language = event.target.value as SummaryOutputLanguage;
              writeSummaryOutputLanguage(language);
              onSummaryOutputLanguageChange(language);
            }}
          >
            <option value="中文">中文</option>
            <option value="English">English</option>
          </select>
        </label>

        <label className="settings-field">
          <span>终端列表分组方式</span>
          <select
            value={terminalGroupingMode}
            onChange={(event) => {
              const mode = event.target.value as TerminalGroupingMode;
              writeTerminalGroupingMode(mode);
              onTerminalGroupingModeChange(mode);
            }}
          >
            <option value="project-topic">项目 / 主题</option>
            <option value="topic">主题</option>
            <option value="time-topic">时间 / 主题 / 子主题</option>
            <option value="project-time-topic">项目 / 时间 / 主题 / 子主题</option>
          </select>
        </label>

        {desktopNotificationsSupported() && (
          <label className="settings-field settings-field-checkbox">
            <span>系统桌面通知</span>
            <input
              type="checkbox"
              checked={desktopNotificationsEnabled}
              onChange={(event) => {
                const enabled = event.target.checked;
                void (async () => {
                  if (enabled) {
                    const permission = await ensureDesktopNotificationPermission();
                    if (permission !== "granted") {
                      writeDesktopNotificationsEnabled(false);
                      onDesktopNotificationsEnabledChange(false);
                      return;
                    }
                  }
                  writeDesktopNotificationsEnabled(enabled);
                  onDesktopNotificationsEnabledChange(enabled);
                })();
              }}
            />
          </label>
        )}

        <p className="muted settings-hint">快捷键：Alt+, 打开设置</p>
      </div>
    </div>
  );
}

export function readInitialSettings() {
  return {
    summaryOutputLanguage: readSummaryOutputLanguage(),
    terminalGroupingMode: readTerminalGroupingMode(),
    desktopNotificationsEnabled: readDesktopNotificationsEnabled()
  };
}
