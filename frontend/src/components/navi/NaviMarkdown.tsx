import React from "react";

interface NaviMarkdownProps {
  content: string;
  className?: string;
}

export const NaviMarkdown: React.FC<NaviMarkdownProps> = ({
  content,
  className = "",
}) => {
  // Convert plain text to properly formatted content
  // Split by newlines and preserve formatting
  const formattedContent = content
    .split('\n')
    .map((line, index) => (
      <React.Fragment key={index}>
        {line || '\u00A0'} {/* Non-breaking space for empty lines */}
        {index < content.split('\n').length - 1 && <br />}
      </React.Fragment>
    ));

  return (
    <div className={`navi-markdown whitespace-pre-wrap ${className}`}>
      {formattedContent}
    </div>
  );
};
