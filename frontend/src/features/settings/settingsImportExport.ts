export function downloadJsonFile(payload: unknown, filename: string): void {
  const blob = new Blob([`${JSON.stringify(payload, null, 2)}\n`], {
    type: "application/json"
  });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

export async function readJsonFile(file: File): Promise<unknown> {
  const text = typeof (file as File & { text?: () => Promise<string> }).text === "function"
    ? await (file as File & { text: () => Promise<string> }).text()
    : await readFileAsText(file);
  return JSON.parse(text) as unknown;
}

export function jsonFilename(id: string): string {
  return `${id.replace(/[^\w.-]+/g, "-")}.json`;
}

function readFileAsText(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result ?? ""));
    reader.onerror = () => reject(reader.error ?? new Error("Failed to read file"));
    reader.readAsText(file);
  });
}
