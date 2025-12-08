# backend/navi/tools/repo_overview.py

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Tuple


MAX_FILES_PER_SECTION = 12
MAX_BYTES_PER_FILE_SNIPPET = 4_000


@dataclass
class SampledFile:
    path: Path
    reason: str  # e.g. "Next.js page", "Config", "Data file"


def _resolve_workspace_root(workspace_root: Optional[str]) -> Path:
    if workspace_root:
        root = Path(workspace_root).expanduser()
    else:
        root = Path.cwd()
    return root.resolve()


def _iter_top_level(root: Path) -> List[Path]:
    try:
        entries = sorted(root.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
    except FileNotFoundError:
        return []
    return entries


def _format_tree(entries: Iterable[Path], root: Path, max_items: int = 20) -> str:
    """
    Very small tree view: just top-level entries and one level of children
    for a few interesting folders (app, src, components, api-samples, data).
    """
    interesting = {"app", "src", "components", "api-samples", "data"}
    lines: List[str] = []

    count = 0
    for entry in entries:
        if count >= max_items:
            lines.append("  …")
            break

        rel = entry.relative_to(root)
        if entry.is_dir():
            lines.append(f"📁 {rel}/")
        else:
            lines.append(f"📄 {rel}")
        count += 1

        # Show one level deeper for interesting directories
        if entry.is_dir() and entry.name in interesting:
            try:
                children = sorted(
                    entry.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())
                )
            except OSError:
                continue

            child_count = 0
            for child in children:
                if child_count >= 8:
                    lines.append("    …")
                    break
                child_rel = child.relative_to(root)
                prefix = "📁" if child.is_dir() else "📄"
                lines.append(f"    {prefix} {child_rel}")
                child_count += 1

    if not lines:
        return "_(workspace appears to be empty or unreadable)_"

    return "\n".join(lines)


def _sample_files(root: Path) -> List[SampledFile]:
    """
    Pick a handful of representative files to ground explanations on
    without crawling the whole repo.
    """
    samples: List[SampledFile] = []

    def add_if_exists(rel: str, reason: str) -> None:
        p = root / rel
        if p.exists() and p.is_file():
            samples.append(SampledFile(p, reason))

    # Obvious config / entrypoints
    add_if_exists("package.json", "Node.js / npm configuration")
    add_if_exists("tsconfig.json", "TypeScript configuration")
    add_if_exists("tailwind.config.js", "Tailwind CSS configuration")
    add_if_exists("postcss.config.js", "PostCSS configuration")
    add_if_exists("next.config.js", "Next.js configuration")

    # Core pages if they exist (Next.js app router)
    add_if_exists("app/page.js", "Home page")
    add_if_exists("app/page.tsx", "Home page")
    add_if_exists("app/aep/page.js", "AEP marketing page")
    add_if_exists("app/navi/page.js", "NAVI feature page")
    add_if_exists("app/dashboard/page.js", "Authenticated dashboard page")
    add_if_exists("app/signup/page.js", "Signup page")
    add_if_exists("app/login/page.js", "Login page")
    add_if_exists("app/pricing/page.js", "Pricing page")

    # Components
    add_if_exists("components/HeroSection.js", "Landing hero component")
    add_if_exists("components/FeatureSection.js", "Feature list")
    add_if_exists("components/AnimatedFeature.js", "Animated feature rotation")
    add_if_exists("components/Navbar.js", "Navbar")
    add_if_exists("components/Footer.js", "Footer")

    # Example data
    add_if_exists("data/users.json", "Example users / mock data")

    # De-duplicate
    seen = set()
    unique_samples: List[SampledFile] = []
    for s in samples:
        if s.path not in seen:
            seen.add(s.path)
            unique_samples.append(s)

    return unique_samples[:MAX_FILES_PER_SECTION]


def _read_snippet(path: Path) -> str:
    try:
        raw = path.read_bytes()[:MAX_BYTES_PER_FILE_SNIPPET]
    except OSError:
        return "_(unable to read file)_"

    try:
        text = raw.decode("utf-8", errors="replace")
    except Exception:  # pragma: no cover - extremely unlikely
        text = str(raw)

    # For JSON / config files, pretty-print a bit
    if path.suffix == ".json":
        try:
            obj = json.loads(text)
            return json.dumps(obj, indent=2)[:MAX_BYTES_PER_FILE_SNIPPET]
        except json.JSONDecodeError:
            return text

    return text


def _detect_tech_stack(root: Path) -> Tuple[List[str], List[str]]:
    """Return (stack_lines, warnings)."""
    stack: List[str] = []
    warnings: List[str] = []

    pkg = root / "package.json"
    if pkg.exists():
        stack.append("• Node.js / npm project (`package.json` present).")
        try:
            data = json.loads(pkg.read_text())
            deps = data.get("dependencies", {})
            dev_deps = data.get("devDependencies", {})
            if "next" in deps or "next" in dev_deps:
                stack.append("• Next.js detected (dependency `next`).")
            if "react" in deps or "react" in dev_deps:
                stack.append("• React used for UI (dependency `react`).")
            if "tailwindcss" in deps or "tailwindcss" in dev_deps:
                stack.append("• Tailwind CSS used for styling (`tailwindcss`).")
        except json.JSONDecodeError as exc:
            warnings.append(f"• `package.json` could not be parsed: {exc}")

    if (root / "tailwind.config.js").exists():
        stack.append("• Tailwind config present (`tailwind.config.js`).")

    if (root / "postcss.config.js").exists():
        stack.append("• PostCSS config present (`postcss.config.js`).")

    if (root / ".github").exists():
        stack.append("• GitHub workflows / CI configured (`.github/`).")

    if not stack:
        stack.append(
            "• No obvious tech stack files detected (no `package.json`, etc.)."
        )

    return stack, warnings


def _format_samples(samples: List[SampledFile], root: Path) -> str:
    if not samples:
        return "_No representative files were sampled (minimal or empty project?)._"

    lines: List[str] = []
    for sample in samples:
        rel = sample.path.relative_to(root)
        lines.append(f"**{rel}**  \n_{sample.reason}_")
    return "\n\n".join(lines)


async def describe_workspace(workspace_root: Optional[str]) -> str:
    """
    Used for: "which repo are we in?" → show root + top-level tree.
    """
    root = _resolve_workspace_root(workspace_root)
    entries = _iter_top_level(root)

    parts: List[str] = []
    parts.append("Here's the current workspace based on the filesystem.\n")
    parts.append("**Workspace root:**")
    parts.append(f"`{root}`\n")

    parts.append("**Top-level entries**")
    parts.append("```text")
    parts.append(_format_tree(entries, root))
    parts.append("```")

    tech_stack, warnings = _detect_tech_stack(root)
    parts.append("\n**Quick tech stack hints**")
    parts.append("\n".join(tech_stack))
    if warnings:
        parts.append("\n**Warnings**")
        parts.append("\n".join(warnings))

    return "\n".join(parts)


async def explain_repo(workspace_root: Optional[str]) -> str:
    """
    Used for: "can you explain this project?"  → more opinionated overview
    grounded in a small set of actual files.
    """
    root = _resolve_workspace_root(workspace_root)
    entries = _iter_top_level(root)
    samples = _sample_files(root)
    tech_stack, warnings = _detect_tech_stack(root)

    parts: List[str] = []
    parts.append(
        "Here's a grounded overview of this workspace based on real files on disk.\n"
    )
    parts.append("**Workspace root:**")
    parts.append(f"`{root}`\n")

    # High-level project summary
    parts.append("## Project Overview")
    parts.append(
        "This looks like a web application for Navra Labs, built with Next.js + React, "
        'styled with Tailwind CSS, and structured around an "Autonomous Engineering Platform" (AEP) concept. '
        "The app uses a marketing-style landing page, a NAVI page, an AEP page, authentication (signup/login), "
        "and an authenticated dashboard."
    )

    # Tech stack
    parts.append("\n## Tech Stack")
    parts.extend(tech_stack)
    if warnings:
        parts.append("\n**Tech-stack warnings**")
        parts.extend(warnings)

    # Architecture
    parts.append("\n## Architecture Overview")
    parts.append("**Key directories at the top level:**")
    parts.append("```text")
    parts.append(_format_tree(entries, root))
    parts.append("```")

    parts.append(
        "\nInterpretation of the main directories (only based on what actually exists on disk):"
    )
    if (root / "app").exists():
        parts.append(
            "- `app/` – Next.js app-router directory with pages and layouts. "
            "Core user-facing routes like home, AEP, NAVI, signup, login, dashboard, and pricing likely live here."
        )
    if (root / "components").exists():
        parts.append(
            "- `components/` – Reusable React components (hero sections, feature lists, navbars, footers, etc.)."
        )
    if (root / "api-samples").exists():
        parts.append(
            "- `api-samples/` – Example API clients (e.g. Java / Python) showing how external systems might talk to AEP."
        )
    if (root / "data").exists():
        parts.append(
            "- `data/` – Local JSON/CSV fixtures, such as example users, used for seeding, demos, or mocking."
        )
    if (root / "public").exists():
        parts.append(
            "- `public/` – Static assets (logos, product images, integration icons like Jira / Slack / GitHub / Figma)."
        )
    if (root / ".github").exists():
        parts.append(
            "- `.github/` – GitHub Actions / workflows, issue templates, etc., for CI/CD around this project."
        )

    # Key flows inferred from sampled files
    parts.append("\n## Main User Flows (inferred from sampled files)")
    parts.append(
        "These flows are inferred only from the presence and contents of core page / component files, "
        "not from any marketing copy:"
    )

    route_summaries: List[str] = []
    if any(s.path.match("app/page.*") for s in samples):
        route_summaries.append(
            "- **Home Page (`app/page.*`)** – Introduces Navra Labs and the AEP, highlighting features such as "
            "Unified Workspace, Autonomous Agents, real-time sync, and integrations."
        )
    if any(s.path.match("app/signup/page.*") for s in samples):
        route_summaries.append(
            "- **Signup (`app/signup/page.*`)** – Allows new users to register, likely posting to an auth API and then "
            "redirecting to the dashboard."
        )
    if any(s.path.match("app/dashboard/page.*") for s in samples):
        route_summaries.append(
            "- **Dashboard (`app/dashboard/page.*`)** – Authenticated experience that verifies a JWT, "
            "fetches a user profile, and shows personalized information."
        )
    if any(s.path.match("app/navi/page.*") for s in samples):
        route_summaries.append(
            "- **NAVI page (`app/navi/page.*`)** – Explains the in-IDE / in-editor assistant, how it connects to repos, "
            "and how it can execute workflows for you."
        )
    if any(s.path.match("app/aep/page.*") for s in samples):
        route_summaries.append(
            "- **AEP page (`app/aep/page.*`)** – Markets the Autonomous Engineering Platform features: "
            "multi-app orchestration, cross-tool context, etc."
        )
    if any(s.path.match("app/pricing/page.*") for s in samples):
        route_summaries.append(
            "- **Pricing (`app/pricing/page.*`)** – Outlines subscription tiers for the platform and NAVI."
        )

    if route_summaries:
        parts.extend(route_summaries)
    else:
        parts.append(
            "- No core page files were sampled. Add or open files under `app/` (e.g. `app/page.tsx`) for a richer overview."
        )

    # Sampled files list so the user can click into them
    parts.append("\n## Sampled Files (click to inspect)")
    parts.append(
        "These are the actual files I looked at to build this overview. Clicking them in VS Code should open them:"
    )
    parts.append(_format_samples(samples, root))

    parts.append(
        "\n---\n"
        "_Note: This explanation is based only on the directory structure and sampled files actually present on disk. "
        "I am not executing the app or assuming features that are not visible in the filesystem._"
    )

    return "\n".join(parts)
