export type UndoSnapshotLike = {
  existed: boolean;
  originalContent?: string;
};

type UndoMetadataInput = {
  actionType?: string;
  existingData?: any;
  snapshot?: UndoSnapshotLike;
};

export function buildUndoRestoreMetadataFromSnapshot(
  input: UndoMetadataInput
): Record<string, any> {
  const { actionType, existingData, snapshot } = input;
  const metadata: Record<string, any> = {};

  if (existingData && typeof existingData === "object") {
    if (typeof existingData.originalContent === "string") {
      metadata.originalContent = existingData.originalContent;
    }
    if (existingData.wasCreated === true) {
      metadata.wasCreated = true;
    }
    if (existingData.wasDeleted === true) {
      metadata.wasDeleted = true;
    }
  }

  // Snapshot metadata is authoritative for unresolved pending undo state.
  if (snapshot) {
    if (snapshot.existed) {
      metadata.originalContent = snapshot.originalContent ?? "";
      if (metadata.wasCreated === true) {
        delete metadata.wasCreated;
      }
    } else {
      metadata.wasCreated = true;
      delete metadata.originalContent;
    }
  }

  const actionTypeLower = String(actionType || "").toLowerCase();
  if (metadata.wasDeleted !== true && actionTypeLower.includes("delete")) {
    metadata.wasDeleted = true;
  }

  return metadata;
}
