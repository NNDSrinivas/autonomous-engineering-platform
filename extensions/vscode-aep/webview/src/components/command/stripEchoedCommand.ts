const normalizePrompt = (line: string): string => {
  let text = line.trim();
  text = text.replace(/^PS [^>]*>\s*/i, "");
  text = text.replace(/^\+\s*/, "");
  text = text.replace(/^[>$#❯➜]\s*/, "");
  return text.trim();
};

export const stripEchoedCommand = (output: string, command: string): string => {
  if (!output || !command) return output;
  const lines = output.split("\n");
  const firstIdx = lines.findIndex((line) => line.trim().length > 0);
  if (firstIdx < 0) return output;
  const normalizedLine = normalizePrompt(lines[firstIdx]);
  const normalizedCommand = command.trim();
  if (!normalizedCommand) return output;
  if (normalizedLine !== normalizedCommand) return output;
  const remaining = lines.slice(firstIdx + 1);
  const hasRemainingContent = remaining.some((line) => line.trim().length > 0);
  if (!hasRemainingContent) return output;
  const nextLines = [...lines.slice(0, firstIdx), ...lines.slice(firstIdx + 1)];
  return nextLines.join("\n");
};
