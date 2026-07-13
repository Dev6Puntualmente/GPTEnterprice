import React from "react";

function renderInline(text: string): React.ReactNode {
  // Regex to split by bold (**), italic (*), code (`), and links ([text](url))
  const parts = text.split(/(\*\*.*?\*\*|\*.*?\*|`.*?`|\[.*?\]\(.*?\))/g);
  return parts.map((part, index) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return <strong key={index} className="font-bold text-white">{part.slice(2, -2)}</strong>;
    }
    if (part.startsWith("*") && part.endsWith("*")) {
      return <em key={index}>{part.slice(1, -1)}</em>;
    }
    if (part.startsWith("`") && part.endsWith("`")) {
      return (
        <code
          key={index}
          className="rounded bg-white/15 px-1 py-0.5 font-mono text-xs text-white"
        >
          {part.slice(1, -1)}
        </code>
      );
    }
    if (part.startsWith("[") && part.includes("](")) {
      const match = part.match(/\[(.*?)\]\((.*?)\)/);
      if (match) {
        const [, linkText, href] = match;
        return (
          <a
            key={index}
            href={href}
            target="_blank"
            rel="noreferrer"
            className="text-blue-400 underline hover:text-blue-300"
          >
            {linkText}
          </a>
        );
      }
    }
    return part;
  });
}

export function Markdown({ content }: { content: string }) {
  const lines = content.split("\n");
  const elements: React.ReactNode[] = [];

  let inList = false;
  let listItems: React.ReactNode[] = [];

  let inTable = false;
  let tableRows: string[][] = [];

  let inCode = false;
  let codeLines: string[] = [];
  let codeLang = "";

  const flushList = (key: string | number) => {
    if (listItems.length > 0) {
      elements.push(
        <ul key={`ul-${key}`} className="list-disc pl-5 mb-2 space-y-1 text-inherit">
          {listItems}
        </ul>
      );
      listItems = [];
      inList = false;
    }
  };

  const flushTable = (key: string | number) => {
    if (tableRows.length > 0) {
      let startIdx = 0;
      let hasHeader = false;

      if (tableRows.length > 1) {
        const secondRow = tableRows[1].join("");
        if (/^[-|\s]+$/.test(secondRow)) {
          hasHeader = true;
          startIdx = 2;
        }
      }

      const headers = hasHeader ? tableRows[0] : null;
      const bodyRows = tableRows.slice(startIdx);

      elements.push(
        <div key={`table-container-${key}`} className="overflow-x-auto my-3 rounded-xl border border-white/10 shadow-lg">
          <table className="min-w-full divide-y divide-white/10 text-left text-xs">
            {headers && (
              <thead className="bg-white/5 font-semibold text-white">
                <tr>
                  {headers.map((h, i) => (
                    <th key={i} className="px-3 py-2 border-b border-white/10 font-bold">
                      {renderInline(h.trim())}
                    </th>
                  ))}
                </tr>
              </thead>
            )}
            <tbody className="divide-y divide-white/10">
              {bodyRows.map((row, rowIndex) => (
                <tr key={rowIndex} className="hover:bg-white/5">
                  {row.map((cell, cellIndex) => (
                    <td key={cellIndex} className="px-3 py-2">
                      {renderInline(cell.trim())}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
      tableRows = [];
      inTable = false;
    }
  };

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    // Code Blocks
    if (line.trim().startsWith("```")) {
      flushList(i);
      flushTable(i);
      if (inCode) {
        elements.push(
          <pre key={`code-${i}`} className="bg-black/35 rounded-xl p-3 my-2 font-mono text-xs overflow-x-auto border border-white/10 text-white">
            <code className={codeLang ? `language-${codeLang}` : ""}>
              {codeLines.join("\n")}
            </code>
          </pre>
        );
        codeLines = [];
        inCode = false;
      } else {
        inCode = true;
        codeLang = line.trim().slice(3);
      }
      continue;
    }

    if (inCode) {
      codeLines.push(line);
      continue;
    }

    // Tables
    if (line.trim().startsWith("|") && line.trim().endsWith("|")) {
      flushList(i);
      inTable = true;
      const cells = line.split("|").slice(1, -1);
      const isSeparator = cells.every((c) => /^[-:\s]+$/.test(c.trim()));
      if (isSeparator && tableRows.length === 1) {
        tableRows.push(cells);
      } else if (!isSeparator || tableRows.length !== 1) {
        tableRows.push(cells);
      }
      continue;
    } else {
      flushTable(i);
    }

    // Lists
    if (line.trim().startsWith("- ") || line.trim().startsWith("* ")) {
      inList = true;
      const content = line.trim().slice(2);
      listItems.push(<li key={`li-${i}`} className="ml-2">{renderInline(content)}</li>);
      continue;
    } else {
      flushList(i);
    }

    // Headers
    if (line.trim().startsWith("### ")) {
      elements.push(<h3 key={i} className="text-sm font-bold mt-3 mb-1 text-white">{renderInline(line.trim().slice(4))}</h3>);
      continue;
    }
    if (line.trim().startsWith("## ")) {
      elements.push(<h2 key={i} className="text-base font-bold mt-4 mb-2 text-white">{renderInline(line.trim().slice(3))}</h2>);
      continue;
    }
    if (line.trim().startsWith("# ")) {
      elements.push(<h1 key={i} className="text-lg font-bold mt-5 mb-3 text-white">{renderInline(line.trim().slice(2))}</h1>);
      continue;
    }

    // Divider
    if (line.trim() === "---") {
      elements.push(<hr key={i} className="my-4 border-white/10" />);
      continue;
    }

    // Paragraph
    if (line.trim()) {
      elements.push(
        <p key={i} className="mb-2 text-inherit">
          {renderInline(line)}
        </p>
      );
    } else {
      // Empty line spacer
      elements.push(<div key={i} className="h-2" />);
    }
  }

  // Clean remaining
  flushList(lines.length);
  flushTable(lines.length);

  return <div className="markdown-body text-inherit">{elements}</div>;
}
