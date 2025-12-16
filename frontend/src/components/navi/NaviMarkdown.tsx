import React from "react";

interface NaviMarkdownProps {
  content: string;
  className?: string;
}

export const NaviMarkdown: React.FC<NaviMarkdownProps> = ({
  content,
  className = "",
}) => {
  return (
    <div
      className={`navi-markdown ${className}`}
      dangerouslySetInnerHTML={{ __html: content }}
    />
  );
};
