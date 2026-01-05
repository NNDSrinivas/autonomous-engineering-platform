/**
 * NAVI Contracts - Shared schemas between extension and backend
 * 
 * This package ensures extension + backend never disagree on:
 * - Intent kind enum values
 * - Plan payload shape  
 * - Tool call/result shape
 * - Fallback behavior for unknown inputs
 */

export * from './intent';
export * from './plan';
export * from './tools';
export * from './context';