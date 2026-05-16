const tableHeaderRegex = /^\s*\|?.+\|.+\|.*$/;
const tableDividerRegex = /^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$/;

export const normalizeTableSpacing = (input: string): string => {
  const lines = input.split(/\r?\n/);
  const output: string[] = [];
  let inFence = false;

  for (let i = 0; i < lines.length; i += 1) {
    const line = lines[i];
    const trimmed = line.trim();

    if (trimmed.startsWith("```")) {
      inFence = !inFence;
      output.push(line);
      continue;
    }

    if (!inFence && tableHeaderRegex.test(line)) {
      const nextLine = lines[i + 1] ?? "";
      const prevLine = output.length > 0 ? output[output.length - 1] : "";
      const needsSpacing = nextLine && tableDividerRegex.test(nextLine) && prevLine.trim() !== "";

      if (needsSpacing) {
        output.push("");
      }
    }

    output.push(line);
  }

  return output.join("\n");
};

export const resolveImageSrc = (src: string | undefined, apiBase: string): string => {
  if (!src) {
    return "";
  }
  if (src.startsWith("http://") || src.startsWith("https://")) {
    return src;
  }
  const normalized = src.startsWith("/") ? src : `/${src}`;
  if (normalized.startsWith("/api/images/")) {
    return `${apiBase}${normalized}`;
  }
  if (normalized.startsWith("/images/")) {
    return `${apiBase}/api${normalized}`;
  }
  return src;
};
