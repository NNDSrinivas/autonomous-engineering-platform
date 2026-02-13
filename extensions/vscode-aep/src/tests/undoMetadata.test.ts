import { test } from "node:test";
import * as assert from "node:assert/strict";
import { buildUndoRestoreMetadataFromSnapshot } from "../undoMetadata";

test("snapshot content wins over per-action content for unresolved multi-run undo", () => {
  const metadata = buildUndoRestoreMetadataFromSnapshot({
    actionType: "editFile",
    existingData: {
      // Later run pre-edit content for same file.
      originalContent: "run-2-pre-edit",
    },
    snapshot: {
      // Earliest unresolved run-start content.
      existed: true,
      originalContent: "run-1-baseline",
    },
  });

  assert.equal(metadata.originalContent, "run-1-baseline");
  assert.equal(metadata.wasCreated, undefined);
});

test("snapshot for newly created file forces delete-style undo semantics", () => {
  const metadata = buildUndoRestoreMetadataFromSnapshot({
    actionType: "writeFile",
    existingData: {
      originalContent: "should-not-be-used",
      wasCreated: false,
    },
    snapshot: {
      existed: false,
    },
  });

  assert.equal(metadata.wasCreated, true);
  assert.equal(metadata.originalContent, undefined);
});

test("without snapshot, existing action metadata is preserved", () => {
  const metadata = buildUndoRestoreMetadataFromSnapshot({
    actionType: "editFile",
    existingData: {
      originalContent: "action-pre-edit",
    },
  });

  assert.equal(metadata.originalContent, "action-pre-edit");
  assert.equal(metadata.wasCreated, undefined);
});

test("delete actions set wasDeleted marker", () => {
  const metadata = buildUndoRestoreMetadataFromSnapshot({
    actionType: "deleteFile",
    existingData: {},
    snapshot: {
      existed: true,
      originalContent: "before-delete",
    },
  });

  assert.equal(metadata.wasDeleted, true);
  assert.equal(metadata.originalContent, "before-delete");
});
