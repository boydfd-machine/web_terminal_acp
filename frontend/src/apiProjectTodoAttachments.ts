import type {
  ProjectTodoAttachment,
  ProjectTodoAttachmentDownload,
  ProjectTodoAttachmentUpload
} from "./types";
import { fetchApi, pathSegment, request, requestVoid, throwApiError } from "./apiCore";

function projectTodoAttachmentPath(clientId: string, projectPath: string, todoId: string, suffix = ""): string {
  const params = new URLSearchParams({ project_path: projectPath });
  return `/api/clients/${pathSegment(clientId)}/projects/todos/${pathSegment(todoId)}${suffix}?${params.toString()}`;
}

export function createProjectTodoAttachmentUpload(
  clientId: string,
  projectPath: string,
  todoId: string,
  input: { filename: string; content_type: string; size_bytes?: number | null }
): Promise<ProjectTodoAttachmentUpload> {
  return request<ProjectTodoAttachmentUpload>(projectTodoAttachmentPath(clientId, projectPath, todoId, "/attachments"), {
    method: "POST",
    body: JSON.stringify({
      filename: input.filename,
      content_type: input.content_type,
      size_bytes: input.size_bytes ?? null
    })
  });
}

export function completeProjectTodoAttachmentUpload(
  clientId: string,
  projectPath: string,
  todoId: string,
  attachmentId: string
): Promise<ProjectTodoAttachment> {
  return request<ProjectTodoAttachment>(
    projectTodoAttachmentPath(clientId, projectPath, todoId, `/attachments/${pathSegment(attachmentId)}/complete`),
    { method: "POST" }
  );
}

export function downloadProjectTodoAttachment(
  clientId: string,
  projectPath: string,
  todoId: string,
  attachmentId: string
): Promise<ProjectTodoAttachmentDownload> {
  return request<ProjectTodoAttachmentDownload>(
    projectTodoAttachmentPath(clientId, projectPath, todoId, `/attachments/${pathSegment(attachmentId)}/download`)
  );
}

export async function deleteProjectTodoAttachment(
  clientId: string,
  projectPath: string,
  todoId: string,
  attachmentId: string
): Promise<void> {
  await requestVoid(
    projectTodoAttachmentPath(clientId, projectPath, todoId, `/attachments/${pathSegment(attachmentId)}`),
    { method: "DELETE" }
  );
}

export async function uploadProjectTodoAttachmentFile(
  clientId: string,
  projectPath: string,
  todoId: string,
  file: File
): Promise<ProjectTodoAttachment> {
  const upload = await createProjectTodoAttachmentUpload(clientId, projectPath, todoId, {
    filename: file.name,
    content_type: file.type || "application/octet-stream",
    size_bytes: file.size
  });
  const response = await fetchApi(upload.upload_url, {
    method: "PUT",
    headers: upload.upload_headers,
    body: file
  });
  if (!response.ok) {
    await throwApiError(response);
  }
  return completeProjectTodoAttachmentUpload(clientId, projectPath, todoId, upload.attachment.id);
}

export const uploadProjectTodoAttachmentImage = uploadProjectTodoAttachmentFile;
