"use client";

import React, { useMemo } from "react";
import { useTheme } from "@/app/components/theme/ThemeProvider";
import type { ThemeColors } from "@/lib/theme/tokens";

type MarkdownStyles = ThemeColors["markdown"];

function renderInline(text: string, styles: MarkdownStyles): React.ReactNode {
  const parts = text.split(/(\*\*.*?\*\*|\*.*?\*|`.*?`|\[.*?\]\(.*?\))/g);
  return parts.map((part, index) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return (
        <strong key={index} style={{ color: styles.strong, fontWeight: 700 }}>
          {part.slice(2, -2)}
        </strong>
      );
    }
    if (part.startsWith("*") && part.endsWith("*") && !part.startsWith("**")) {
      return (
        <em key={index} style={{ color: styles.body }}>
          {part.slice(1, -1)}
        </em>
      );
    }
    if (part.startsWith("`") && part.endsWith("`")) {
      return (
        <code
          key={index}
          className="rounded px-1.5 py-0.5 font-mono text-xs"
          style={{ background: styles.codeBg, color: styles.codeText }}
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
            className="underline underline-offset-2"
            style={{ color: styles.link }}
          >
            {linkText}
          </a>
        );
      }
    }
    return <span key={index}>{part}</span>;
  });
}

export function Markdown({
  content,
  inverted = false,
}: {
  content: string;
  inverted?: boolean;
}) {
  const { colors } = useTheme();
  const styles = inverted
    ? {
        heading: "#ffffff",
        strong: "#ffffff",
        body: "rgba(255,255,255,0.92)",
        muted: "rgba(255,255,255,0.7)",
        link: "#c7d2fe",
        linkHover: "#e0e7ff",
        codeBg: "rgba(255,255,255,0.14)",
        codeText: "#f8fafc",
        codeBlockBg: "rgba(0,0,0,0.25)",
        codeBlockText: "#f1f5f9",
        border: "rgba(255,255,255,0.18)",
        tableHeadBg: "rgba(255,255,255,0.08)",
        tableRowHover: "rgba(255,255,255,0.06)",
        hr: "rgba(255,255,255,0.2)",
      }
    : colors.markdown;

  const elements = useMemo(() => {
    const lines = content.split("\n");
    const nodes: React.ReactNode[] = [];

    let inList = false;
    let listItems: React.ReactNode[] = [];
    let inTable = false;
    let tableRows: string[][] = [];
    let inCode = false;
    let codeLines: string[] = [];
    let codeLang = "";

    const flushList = (key: string | number) => {
      if (listItems.length > 0) {
        nodes.push(
          <ul
            key={`ul-${key}`}
            className="mb-2 list-disc space-y-1 pl-5"
            style={{ color: styles.body }}
          >
            {listItems}
          </ul>,
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

        nodes.push(
          <div
            key={`table-container-${key}`}
            className="my-3 max-w-full overflow-x-auto rounded-xl shadow-sm"
            style={{ border: `1px solid ${styles.border}` }}
          >
            <table className="min-w-full text-left text-xs" style={{ color: styles.body }}>
              {headers ? (
                <thead style={{ background: styles.tableHeadBg, color: styles.heading }}>
                  <tr>
                    {headers.map((h, i) => (
                      <th
                        key={i}
                        className="px-3 py-2 font-bold"
                        style={{ borderBottom: `1px solid ${styles.border}` }}
                      >
                        {renderInline(h.trim(), styles)}
                      </th>
                    ))}
                  </tr>
                </thead>
              ) : null}
              <tbody>
                {bodyRows.map((row, rowIndex) => (
                  <tr
                    key={rowIndex}
                    style={{ borderTop: rowIndex > 0 ? `1px solid ${styles.border}` : undefined }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.background = styles.tableRowHover;
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.background = "transparent";
                    }}
                  >
                    {row.map((cell, cellIndex) => (
                      <td key={cellIndex} className="px-3 py-2">
                        {renderInline(cell.trim(), styles)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>,
        );
        tableRows = [];
        inTable = false;
      }
    };

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];

      if (line.trim().startsWith("```")) {
        flushList(i);
        flushTable(i);
        if (inCode) {
          nodes.push(
            <pre
              key={`code-${i}`}
              className="my-2 overflow-x-auto rounded-xl p-3 font-mono text-xs"
              style={{
                background: styles.codeBlockBg,
                color: styles.codeBlockText,
                border: `1px solid ${styles.border}`,
              }}
            >
              <code className={codeLang ? `language-${codeLang}` : ""}>
                {codeLines.join("\n")}
              </code>
            </pre>,
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
      }
      flushTable(i);

      if (line.trim().startsWith("- ") || line.trim().startsWith("* ")) {
        inList = true;
        const itemContent = line.trim().slice(2);
        listItems.push(
          <li key={`li-${i}`} className="ml-2">
            {renderInline(itemContent, styles)}
          </li>,
        );
        continue;
      }
      flushList(i);

      if (line.trim().startsWith("### ")) {
        nodes.push(
          <h3
            key={i}
            className="mb-1 mt-3 text-sm font-bold"
            style={{ color: styles.heading }}
          >
            {renderInline(line.trim().slice(4), styles)}
          </h3>,
        );
        continue;
      }
      if (line.trim().startsWith("## ")) {
        nodes.push(
          <h2
            key={i}
            className="mb-2 mt-4 text-base font-bold"
            style={{ color: styles.heading }}
          >
            {renderInline(line.trim().slice(3), styles)}
          </h2>,
        );
        continue;
      }
      if (line.trim().startsWith("# ")) {
        nodes.push(
          <h1
            key={i}
            className="mb-3 mt-5 text-lg font-bold"
            style={{ color: styles.heading }}
          >
            {renderInline(line.trim().slice(2), styles)}
          </h1>,
        );
        continue;
      }

      if (line.trim() === "---") {
        nodes.push(
          <hr key={i} className="my-4" style={{ borderColor: styles.hr, borderTopWidth: 1 }} />,
        );
        continue;
      }

      if (line.trim()) {
        nodes.push(
          <p key={i} className="mb-2" style={{ color: styles.body }}>
            {renderInline(line, styles)}
          </p>,
        );
      } else {
        nodes.push(<div key={i} className="h-2" />);
      }
    }

    flushList(lines.length);
    flushTable(lines.length);
    return nodes;
  }, [content, styles]);

  return (
    <div className="markdown-body min-w-0 max-w-full break-words" style={{ color: styles.body }}>
      {elements}
    </div>
  );
}
