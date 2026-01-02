import * as vscode from 'vscode';
import * as path from 'path';
import * as Diff from 'diff';
import { applyUnifiedDiff } from '../diffUtils';

type PatchTarget = {
  uri: vscode.Uri;
  isDelete: boolean;
  isNewFile: boolean;
  patchText: string;
};

function stripPatchPath(raw?: string): string | null {
  if (!raw) return null;
  const cleaned = raw.split('\t')[0].trim();
  if (!cleaned || cleaned === '/dev/null') return null;
  if (cleaned.startsWith('a/')) return cleaned.slice(2);
  if (cleaned.startsWith('b/')) return cleaned.slice(2);
  return cleaned;
}

function resolvePatchTargets(
  patchText: string,
  filePath?: string
): PatchTarget[] {
  const patches = Diff.parsePatch(patchText);
  if (!patches || patches.length === 0) {
    throw new Error('Invalid or empty patch provided');
  }

  const workspaceRoot = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || '';
  const targets: PatchTarget[] = [];

  for (const patch of patches) {
    const oldPath = stripPatchPath(patch.oldFileName);
    const newPath = stripPatchPath(patch.newFileName);
    const resolvedPath = filePath || newPath || oldPath;

    if (!resolvedPath) {
      continue;
    }

    const targetPath = path.isAbsolute(resolvedPath)
      ? resolvedPath
      : path.join(workspaceRoot, resolvedPath);

    const isDelete = !newPath && !!oldPath;
    const isNewFile = !oldPath && !!newPath;

    targets.push({
      uri: vscode.Uri.file(targetPath),
      isDelete,
      isNewFile,
      patchText: Diff.formatPatch(patch),
    });
  }

  return targets;
}

async function readDocumentText(uri: vscode.Uri): Promise<string> {
  try {
    const openDoc = vscode.workspace.textDocuments.find(doc => doc.uri.fsPath === uri.fsPath);
    if (openDoc) {
      return openDoc.getText();
    }
    const doc = await vscode.workspace.openTextDocument(uri);
    return doc.getText();
  } catch {
    const bytes = await vscode.workspace.fs.readFile(uri);
    return new TextDecoder('utf-8').decode(bytes);
  }
}

export async function applyUnifiedPatch(content: string, filePath?: string): Promise<boolean> {
  console.log('applyUnifiedPatch called with:', { content: content?.length || 0, filePath });

  try {
    const targets = resolvePatchTargets(content, filePath);
    if (targets.length === 0) {
      throw new Error('No patch targets resolved');
    }

    const edits = new vscode.WorkspaceEdit();
    let hadError = false;

    for (const target of targets) {
      try {
        if (target.isDelete) {
          edits.deleteFile(target.uri, { ignoreIfNotExists: true });
          continue;
        }

        const original = target.isNewFile ? '' : await readDocumentText(target.uri);
        const updated = applyUnifiedDiff(original, target.patchText);

        if (target.isNewFile) {
          edits.createFile(target.uri, { ignoreIfExists: true });
          edits.insert(target.uri, new vscode.Position(0, 0), updated);
          continue;
        }

        const document = await vscode.workspace.openTextDocument(target.uri);
        const fullRange = new vscode.Range(0, 0, document.lineCount, 0);
        edits.replace(target.uri, fullRange, updated);
      } catch (error) {
        console.error('Patch application failed for target:', target.uri.fsPath, error);
        hadError = true;
      }
    }

    if (edits.size === 0) {
      throw new Error('Patch contained no applicable edits');
    }

    const applied = await vscode.workspace.applyEdit(edits);
    return applied && !hadError;
  } catch (error) {
    console.error('applyUnifiedPatch failed:', error);
    return false;
  }
}
