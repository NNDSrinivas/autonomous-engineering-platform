const normalizePrompt = (line: string): string => {
  let text = line.trim();
  text = text.replace(/^PS [^>]*>\s*/i, "");
  text = text.replace(/^\+\s*/, "");
  text = text.replace(/^[>$#❯➜]\s*/, "");
  return text.trim();
};

export const stripEchoedCommand = (output: string, command: string): string => {
  if (!output || !command) return output;
  const outputLines = output.split("\n");
  const commandLines = command
    .split("\n")
    .map((line) => line.replace(/\r$/, ""))
    .filter((line, idx, arr) => !(idx === arr.length - 1 && line.trim().length === 0));

  if (commandLines.length === 0) return output;

  const firstOutputIdx = outputLines.findIndex((line) => line.trim().length > 0);
  if (firstOutputIdx < 0) return output;

  const matches = commandLines.every((commandLine, index) => {
    const outputLine = outputLines[firstOutputIdx + index];
    if (outputLine === undefined) return false;
    if (index === 0) {
      return normalizePrompt(outputLine) === commandLine.trim();
    }
    return outputLine.replace(/\r$/, "").trimEnd() === commandLine.trimEnd();
  });

  if (!matches) return output;

  const stripped = [
    ...outputLines.slice(0, firstOutputIdx),
    ...outputLines.slice(firstOutputIdx + commandLines.length),
  ];
  const hasContent = stripped.some((line) => line.trim().length > 0);
  return hasContent ? stripped.join("\n") : "";
};
