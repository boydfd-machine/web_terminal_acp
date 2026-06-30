import importlib


def test_workspace_context_is_canonical_for_legacy_imports():
    module_pairs = [
        ("app.contexts.workspace.api.folders_routes", "app.routers.folders"),
        ("app.contexts.workspace.api.projects_routes", "app.routers.projects"),
        ("app.contexts.workspace.api.project_todos_routes", "app.routers.project_todos"),
        ("app.contexts.workspace.api.project_summaries_routes", "app.routers.project_summaries"),
        ("app.contexts.workspace.application.folders_service", "app.services.folders_api"),
        ("app.contexts.workspace.application.project_files", "app.services.project_files"),
        (
            "app.contexts.workspace.application.project_todo_dispatch",
            "app.services.project_todo_dispatch",
        ),
        (
            "app.contexts.workspace.application.project_browse_roots",
            "app.services.project_browse_roots",
        ),
        (
            "app.contexts.workspace.application.project_summaries_service",
            "app.services.project_summaries_api",
        ),
        ("app.contexts.workspace.application.project_summarizer", "app.services.project_summarizer"),
        ("app.contexts.workspace.application.folder_splitter", "app.services.folder_splitter"),
        (
            "app.contexts.workspace.application.folder_split_worker",
            "app.services.folder_split_worker",
        ),
        ("app.contexts.workspace.application.summarizer", "app.services.summarizer"),
        (
            "app.contexts.workspace.application.summary_scheduler",
            "app.services.summary_scheduler",
        ),
        ("app.contexts.workspace.application.summary_worker", "app.services.summary_worker"),
        ("app.contexts.workspace.domain.folders", "app.domain.folders"),
        ("app.contexts.workspace.domain.project_summaries", "app.domain.project_summaries"),
        ("app.contexts.workspace.infrastructure.folders_repository", "app.repositories.folders"),
        (
            "app.contexts.workspace.infrastructure.project_summaries_repository",
            "app.repositories.project_summaries",
        ),
        (
            "app.contexts.workspace.infrastructure.folder_split_jobs_repository",
            "app.repositories.folder_split_jobs",
        ),
        (
            "app.contexts.workspace.infrastructure.project_todos_repository",
            "app.repositories.project_todos",
        ),
        (
            "app.contexts.workspace.infrastructure.summary_jobs_repository",
            "app.repositories.summary_jobs",
        ),
    ]
    for context_path, legacy_path in module_pairs:
        context_module = importlib.import_module(context_path)
        legacy_module = importlib.import_module(legacy_path)
        assert legacy_module is context_module


def test_workspace_schemas_are_owned_by_context():
    context_schemas = importlib.import_module("app.contexts.workspace.api.schemas")
    schemas = importlib.import_module("app.schemas")

    for name in (
        "FolderCreateIn",
        "FolderOut",
        "ProjectBrowseRootListOut",
        "ProjectBrowseRootOut",
        "ProjectFileContentOut",
        "ProjectFileEntryOut",
        "ProjectFileListOut",
        "ProjectFileSaveIn",
        "ProjectFileUploadIn",
        "ProjectFileUploadOut",
        "ProjectOut",
        "ProjectSummaryOut",
        "ProjectSummarySummarizeIn",
        "ProjectTodoCreateIn",
        "ProjectTodoDispatchIn",
        "ProjectTodoListItemOut",
        "ProjectTodoListOut",
        "ProjectTodoOut",
        "ProjectTodoPatchIn",
        "ProjectTodoReferenceOut",
        "ProjectTodoRelationOut",
        "TerminalProjectOut",
    ):
        assert getattr(schemas, name) is getattr(context_schemas, name)
