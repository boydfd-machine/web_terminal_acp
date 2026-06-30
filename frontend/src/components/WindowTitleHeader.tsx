import { useI18n } from "../i18n";
import { MAX_TITLE_LENGTH } from "./windowDetailData";

type WindowTitleHeaderProps = {
  isEditingTitle: boolean;
  renameError: unknown;
  renamePending: boolean;
  title: string;
  titleDraft: string;
  titleSaveDisabled: boolean;
  onBeginEdit: () => void;
  onCancelEdit: () => void;
  onSubmit: () => void;
  onTitleDraftChange: (title: string) => void;
};

export function WindowTitleHeader({
  isEditingTitle,
  renameError,
  renamePending,
  title,
  titleDraft,
  titleSaveDisabled,
  onBeginEdit,
  onCancelEdit,
  onSubmit,
  onTitleDraftChange
}: WindowTitleHeaderProps) {
  const { t } = useI18n();

  return (
    <>
      <div className="window-title-header">
        {isEditingTitle ? (
          <form
            className="window-title-form"
            onSubmit={(event) => {
              event.preventDefault();
              if (!titleSaveDisabled) {
                onSubmit();
              }
            }}
          >
            <input
              aria-label={t("terminal.titleLabel")}
              maxLength={MAX_TITLE_LENGTH}
              value={titleDraft}
              autoFocus
              disabled={renamePending}
              onChange={(event) => onTitleDraftChange(event.target.value)}
            />
            <div className="window-title-actions">
              <button type="submit" disabled={titleSaveDisabled}>
                {t("common.save")}
              </button>
              <button type="button" disabled={renamePending} onClick={onCancelEdit}>
                {t("common.cancel")}
              </button>
            </div>
          </form>
        ) : (
          <div className="window-title-display">
            <h2 title={title}>{title}</h2>
            <button type="button" className="window-title-edit-button" onClick={onBeginEdit}>
              {t("common.edit")}
            </button>
          </div>
        )}
      </div>
      {renameError !== null && (
        <p className="error" role="alert">
          {renameError instanceof Error ? renameError.message : t("window.detail.renameFailed")}
        </p>
      )}
    </>
  );
}
