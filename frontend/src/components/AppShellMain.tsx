import type { RefObject } from "react";

import { AppDetailPanel } from "./AppDetailPanel";
import { AppSidebar } from "./AppSidebar";
import { AppToolbar } from "./AppToolbar";
import { ProjectFileTabsBar, type ProjectFileTabsBarProps } from "./ProjectFileTabsBar";
import { TerminalDrawer } from "./TerminalDrawer";
import { TerminalMainPane } from "./TerminalMainPane";
import type { TerminalPaneHandle } from "./TerminalPane";
import type { AppSidebarProps } from "./AppSidebar";
import type { AppToolbarProps } from "./AppToolbar";
import type { TerminalMainPaneProps } from "./TerminalMainPane";
import type { AppDetailPanelProps } from "./AppDetailPanel";
import type { TerminalDrawerProps } from "./TerminalDrawer";
import type { WorkspaceMode } from "../appState";

type AppShellMainProps = {
  detailPanelProps: AppDetailPanelProps;
  sidebarProps: AppSidebarProps;
  terminalDrawer: {
    mounted: boolean;
    props: TerminalDrawerProps | null;
  };
  projectFileTabsBarProps: ProjectFileTabsBarProps;
  terminalMainPaneProps: TerminalMainPaneProps;
  toolbarProps: AppToolbarProps;
  workspaceMode: WorkspaceMode;
  workspaceRef: RefObject<HTMLElement>;
};

export function AppShellMain({
  detailPanelProps,
  sidebarProps,
  terminalDrawer,
  projectFileTabsBarProps,
  terminalMainPaneProps,
  toolbarProps,
  workspaceMode,
  workspaceRef,
}: AppShellMainProps) {
  return (
    <>
      <AppSidebar {...sidebarProps} />
      <section className="workspace" data-debug-id="workspace" ref={workspaceRef}>
        <AppToolbar {...toolbarProps} />
        {workspaceMode === "files" && <ProjectFileTabsBar {...projectFileTabsBarProps} />}
        <TerminalMainPane {...terminalMainPaneProps} />
        {terminalDrawer.mounted
          && terminalDrawer.props !== null
          && (workspaceMode === "terminal" || terminalDrawer.props.mode === "terminal") && (
          <TerminalDrawer {...terminalDrawer.props} />
        )}
      </section>
      <AppDetailPanel {...detailPanelProps} />
    </>
  );
}

export type {
  AppDetailPanelProps,
  AppSidebarProps,
  AppToolbarProps,
  ProjectFileTabsBarProps,
  TerminalDrawerProps,
  TerminalMainPaneProps,
  TerminalPaneHandle,
};
