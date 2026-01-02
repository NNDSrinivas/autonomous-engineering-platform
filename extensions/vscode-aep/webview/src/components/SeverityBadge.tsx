import React from "react";
import clsx from "clsx";

export default function SeverityBadge({ severity }: { severity: string }) {
  return (
    <span
      className={clsx(
        "text-xs px-2 py-1 rounded-full font-semibold",
        {
          "bg-red-100 text-red-700": severity === "high",
          "bg-yellow-100 text-yellow-800": severity === "medium",
          "bg-green-100 text-green-800": severity === "low",
        }
      )}
    >
      {severity.toUpperCase()}
    </span>
  );
}