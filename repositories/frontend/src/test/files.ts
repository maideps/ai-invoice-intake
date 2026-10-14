import { File as NodeFile } from "node:buffer";

/**
 * A file for uploads in tests. Node's File (not jsdom's) so that Node's fetch can send it in a
 * multipart body; browsers have no such split.
 */
export function testFile(content: string, name: string, type = "application/pdf"): File {
  return new NodeFile([content], name, { type }) as unknown as File;
}

export const pdfFile = (name: string) => testFile("%PDF-1.4 test", name);
