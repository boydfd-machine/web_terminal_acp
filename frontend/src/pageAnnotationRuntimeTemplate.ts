export function runtimeHtml(): string {
  return `
    <style>${runtimeCss()}</style>
    <button class="page-annotation-button" type="button" aria-label="Page annotation mode" title="Page annotation mode" aria-pressed="false">+</button>
    <div class="page-annotation-overlay" hidden>
      <div class="page-annotation-scrim"></div>
      <div class="page-annotation-rectangle" hidden></div>
      <form class="page-annotation-form" hidden>
        <div class="page-annotation-targets" role="group" aria-label="Annotation target">
          <button type="button" data-page-annotation-target="new" aria-pressed="true">New card</button>
          <button type="button" data-page-annotation-target="existing" aria-pressed="false">Existing card</button>
        </div>
        <label class="page-annotation-todo-field" hidden>
          <span>Card</span>
          <select class="page-annotation-todo-select"></select>
        </label>
        <label>
          <span>User command</span>
          <textarea rows="5" placeholder="Enter the command to follow for this selected area"></textarea>
        </label>
        <label class="page-annotation-screenshot">
          <input class="page-annotation-screenshot-input" type="checkbox">
          <span class="page-annotation-screenshot-label">Attach screenshot</span>
        </label>
        <a class="page-annotation-screenshot-help" href="/docs/page-annotation-screenshots.html" target="_blank" rel="noreferrer" hidden>How to enable screenshots</a>
        <p class="page-annotation-error" role="alert"></p>
        <div class="page-annotation-actions">
          <button class="page-annotation-cancel" type="button">Cancel</button>
          <button type="submit">Create card</button>
        </div>
      </form>
    </div>
  `;
}

function runtimeCss(): string {
  return `
    :host {
      all: initial;
      color-scheme: light dark;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    .page-annotation-button {
      position: fixed;
      z-index: 2147483640;
      top: 10px;
      left: 10px;
      width: 34px;
      height: 34px;
      border: 1px solid rgba(15, 23, 42, 0.24);
      border-radius: 8px;
      background: rgba(248, 250, 252, 0.96);
      color: #0f172a;
      box-shadow: 0 8px 20px rgba(15, 23, 42, 0.18);
      cursor: crosshair;
      font: 700 22px/1 ui-sans-serif, system-ui;
    }
    .page-annotation-button[aria-pressed="true"] {
      background: #0f766e;
      color: white;
    }
    .page-annotation-overlay {
      position: fixed;
      z-index: 2147483639;
      inset: 0;
      cursor: crosshair;
    }
    .page-annotation-scrim {
      position: absolute;
      inset: 0;
      background: rgba(15, 23, 42, 0.14);
      pointer-events: none;
    }
    .page-annotation-rectangle {
      position: fixed;
      border: 2px solid #0f766e;
      background: rgba(20, 184, 166, 0.16);
      box-shadow: 0 0 0 9999px rgba(15, 23, 42, 0.18);
      pointer-events: none;
    }
    .page-annotation-form {
      position: fixed;
      z-index: 2147483641;
      width: min(360px, calc(100vw - 24px));
      border: 1px solid rgba(15, 23, 42, 0.16);
      border-radius: 8px;
      background: #ffffff;
      color: #111827;
      box-shadow: 0 18px 40px rgba(15, 23, 42, 0.24);
      padding: 12px;
      cursor: default;
    }
    .page-annotation-form label {
      display: grid;
      gap: 7px;
      color: #111827;
      font: 600 13px/1.3 ui-sans-serif, system-ui;
    }
    .page-annotation-form textarea {
      box-sizing: border-box;
      width: 100%;
      min-height: 112px;
      resize: vertical;
      border: 1px solid #cbd5e1;
      border-radius: 7px;
      padding: 9px;
      color: #111827;
      background: #ffffff;
      font: 400 13px/1.45 ui-sans-serif, system-ui;
    }
    .page-annotation-todo-select {
      box-sizing: border-box;
      width: 100%;
      min-height: 34px;
      border: 1px solid #cbd5e1;
      border-radius: 7px;
      padding: 7px;
      color: #111827;
      background: #ffffff;
      font: 400 13px/1.35 ui-sans-serif, system-ui;
    }
    .page-annotation-screenshot {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-top: 9px;
      color: #111827;
      font: 600 13px/1.3 ui-sans-serif, system-ui;
    }
    .page-annotation-screenshot input {
      width: 16px;
      height: 16px;
      margin: 0;
      accent-color: #0f766e;
    }
    .page-annotation-screenshot-help {
      display: inline-block;
      margin-top: 5px;
      color: #0f766e;
      font: 600 12px/1.35 ui-sans-serif, system-ui;
      text-decoration: underline;
      text-underline-offset: 2px;
    }
    .page-annotation-screenshot-help[hidden] {
      display: none;
    }
    .page-annotation-targets {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 6px;
      margin-bottom: 10px;
    }
    .page-annotation-targets button[aria-pressed="true"] {
      border-color: #0f766e;
      background: rgba(15, 118, 110, 0.12);
      color: #134e4a;
    }
    .page-annotation-actions {
      display: flex;
      justify-content: flex-end;
      gap: 8px;
      margin-top: 10px;
    }
    .page-annotation-form button {
      border: 1px solid #cbd5e1;
      border-radius: 7px;
      background: #f8fafc;
      color: #0f172a;
      padding: 7px 10px;
      font: 600 13px/1 ui-sans-serif, system-ui;
      cursor: pointer;
    }
    .page-annotation-form button[type="submit"] {
      border-color: #0f766e;
      background: #0f766e;
      color: white;
    }
    .page-annotation-form button:disabled {
      cursor: wait;
      opacity: 0.68;
    }
    .page-annotation-error {
      min-height: 18px;
      margin: 8px 0 0;
      color: #b91c1c;
      font: 500 12px/1.4 ui-sans-serif, system-ui;
    }
  `;
}
