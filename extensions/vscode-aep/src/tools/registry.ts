import { ToolHandler } from "./types";
import { scanProblems } from "./scanProblems";
import { analyzeProblems } from "./analyzeProblems";
import { applyFixes } from "./applyFixes";
import { verifyProblems } from "./verifyProblems";

export const toolRegistry: Record<string, ToolHandler> = {
    scanProblems,
    analyzeProblems,
    applyFixes,
    verifyProblems
};