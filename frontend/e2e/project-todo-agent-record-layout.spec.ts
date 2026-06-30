import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { expect, test } from "@playwright/test";

const styles = readFileSync(
  resolve(dirname(fileURLToPath(import.meta.url)), "../src/styles/agent-chat.css"),
  "utf8"
) + readFileSync(
  resolve(dirname(fileURLToPath(import.meta.url)), "../src/styles/project-todo-detail-shell.css"),
  "utf8"
) + readFileSync(
  resolve(dirname(fileURLToPath(import.meta.url)), "../src/styles/project-todo-agent-record.css"),
  "utf8"
) + readFileSync(
  resolve(dirname(fileURLToPath(import.meta.url)), "../src/styles/project-todo-detail-layout.css"),
  "utf8"
) + readFileSync(
  resolve(dirname(fileURLToPath(import.meta.url)), "../src/styles/project-todo-actions.css"),
  "utf8"
);

function fixture(messageClass: string): string {
  const longText = "This is a long inline todo agent preview message ".repeat(100);

  return `<!doctype html>
    <html>
      <head><style>${styles}</style></head>
      <body class="theme-skin-default">
        <div class="project-todo-detail-backdrop">
          <section class="project-todo-detail-dialog">
            <header class="project-todo-detail-header">
              <div class="project-todo-detail-heading"><h2>Todo detail</h2></div>
            </header>
            <div class="project-todo-detail-body">
              <div class="project-todo-detail-main">
                <section class="project-todo-detail-description-panel">
                  <div class="project-todo-detail-description">description</div>
                </section>
                <section class="project-todo-execution-terminals">
                  <div class="project-todo-agent-record">
                    <header class="project-todo-agent-record-header">
                      <strong>Agent conversation</strong>
                      <button class="project-todo-detail-icon-button project-todo-agent-record-preview-button">expand</button>
                    </header>
                    <div class="project-todo-agent-record-stats"><span>1 messages</span></div>
                    <div class="project-todo-agent-record-list" aria-label="Recent agent messages">
                      <article class="${messageClass}">
                        <div class="agent-chat-avatar agent-chat-avatar-agent project-todo-agent-record-avatar"></div>
                        <div class="project-todo-agent-record-message-content">
                          <button class="project-todo-agent-record-message-expand">expand</button>
                          <p>${longText}</p>
                        </div>
                      </article>
                    </div>
                  </div>
                </section>
              </div>
              <aside class="project-todo-detail-side">
                <section class="project-todo-metadata-panel">
                  <header><strong>Metadata</strong></header>
                </section>
              </aside>
            </div>
          </section>
        </div>
      </body>
    </html>`;
}

test.describe("project todo agent record layout", () => {
  for (const messageClass of [
    "project-todo-agent-record-item-agent",
    "project-todo-agent-record-item-subagent-call",
    "project-todo-agent-record-item-subagent-result"
  ]) {
    test(`keeps ${messageClass} preview messages wider than the avatar column`, async ({ page }) => {
      await page.setViewportSize({ width: 1440, height: 900 });
      await page.setContent(fixture(messageClass));

      const metrics = await page.evaluate(() => {
        const article = document.querySelector(".project-todo-agent-record-list article");
        const bubble = document.querySelector(".project-todo-agent-record-message-content");
        const body = document.querySelector(".project-todo-agent-record-message-content p");
        const avatar = document.querySelector(".project-todo-agent-record-avatar");

        if (!(article instanceof HTMLElement)
          || !(bubble instanceof HTMLElement)
          || !(body instanceof HTMLElement)
          || !(avatar instanceof HTMLElement)) {
          throw new Error("Missing todo agent record fixture elements");
        }

        const articleStyle = window.getComputedStyle(article);
        return {
          articleColumns: articleStyle.gridTemplateColumns,
          articleWidth: article.getBoundingClientRect().width,
          avatarWidth: avatar.getBoundingClientRect().width,
          bubbleWidth: bubble.getBoundingClientRect().width,
          bodyWidth: body.getBoundingClientRect().width,
        };
      });

      expect(metrics.articleWidth).toBeGreaterThan(600);
      expect(metrics.bubbleWidth).toBeGreaterThan(metrics.avatarWidth * 10);
      expect(metrics.bodyWidth).toBeGreaterThan(metrics.avatarWidth * 8);
      expect(metrics.articleColumns).toMatch(/px 30px$/);
    });
  }
});
