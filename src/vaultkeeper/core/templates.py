"""Template discovery, variable interpolation, and standard note templating engine."""

import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from ..exceptions import CreationError, TemplateError
from ..models import VaultConfig
from .document import MarkdownDocument


def resolve_target_folder(
    vault_root: Path,
    tipo: str,
    custom_folder: Optional[Union[str, Path]] = None,
) -> Path:
    """Resolve the destination directory for a new note.

    If custom_folder is provided:
        - Resolves relative to vault_root (or validates absolute path within vault_root).
    Otherwise:
        - Applies Johnny.Decimal routing rules based on tipo:
          * 'Progetto' -> folder matching '10-19_*' or containing 'progett'
          * 'Contatto' -> folder matching '32_CRM' or '30-39_*'
          * 'Risorsa'  -> folder matching '20-29_*' or containing 'risors'
          * 'Appunto'  -> folder matching '20-29_*' or first area directory
          * 'Sistema'  -> folder matching '01-09_*' or '00-09_*'
          * Fallback   -> vault_root

    Args:
        vault_root: Root path of the vault.
        tipo: Note classification type.
        custom_folder: Optional explicit target folder.

    Returns:
        Resolved Path for the target folder.

    Raises:
        CreationError: If custom_folder resolves outside the vault root.
    """
    if custom_folder is not None:
        p = Path(custom_folder)
        resolved = (vault_root / p if not p.is_absolute() else p).resolve()
        try:
            resolved.relative_to(vault_root.resolve())
        except ValueError:
            raise CreationError(f"Target folder '{custom_folder}' is outside vault root: {vault_root}")
        return resolved

    # Auto-routing based on Johnny.Decimal conventions
    norm_tipo = tipo.strip().lower()

    # Discover candidate top-level directories (excluding hidden / ignored)
    subdirs: List[Path] = [
        d
        for d in vault_root.iterdir()
        if d.is_dir()
        and not d.name.startswith(".")
        and d.name not in (".obsidian", ".trash", ".git", "node_modules", ".venv")
    ]

    # Meta folders (00-09, 01-09, system) are excluded for general note routing
    content_subdirs: List[Path] = [
        d
        for d in subdirs
        if not (d.name.startswith("00-09") or d.name.startswith("01-09") or "sistema" in d.name.lower())
    ]

    if norm_tipo == "progetto":
        for d in sorted(content_subdirs, key=lambda x: x.name):
            if d.name.startswith("10-19") or "progett" in d.name.lower():
                return d

    elif norm_tipo == "contatto":
        # Check for 32_CRM recursively under 30-39 or any top-level CRM
        for d in sorted(content_subdirs, key=lambda x: x.name):
            if d.name.startswith("30-39") or "carrier" in d.name.lower():
                crm_sub = d / "32_CRM"
                if crm_sub.is_dir():
                    return crm_sub
                # Check any direct subfolder containing CRM
                for sub in d.iterdir():
                    if sub.is_dir() and "crm" in sub.name.lower():
                        return sub
                return d
        for d in sorted(content_subdirs, key=lambda x: x.name):
            if "crm" in d.name.lower() or "contatt" in d.name.lower():
                return d

    elif norm_tipo == "risorsa":
        for d in sorted(content_subdirs, key=lambda x: x.name):
            if "risors" in d.name.lower():
                return d
        for d in sorted(content_subdirs, key=lambda x: x.name):
            if d.name.startswith("20-29"):
                return d

    elif norm_tipo == "appunto":
        for d in sorted(content_subdirs, key=lambda x: x.name):
            if d.name.startswith("20-29") or "are" in d.name.lower() or "istruzion" in d.name.lower():
                return d

    elif norm_tipo == "sistema":
        for d in sorted(subdirs, key=lambda x: x.name):
            if d.name.startswith("01-09") or d.name.startswith("00-09") or "sistema" in d.name.lower():
                return d

    # Fallback to first 20-29 area if available, else vault_root
    for d in sorted(content_subdirs, key=lambda x: x.name):
        if d.name.startswith("20-29"):
            return d

    return vault_root


class TemplateEngine:
    """Discovers, renders, and interpolates Markdown note templates."""

    def __init__(self, config: VaultConfig) -> None:
        self.config = config

    def get_templates_folder(self) -> Optional[Path]:
        """Locate the active templates folder, checking configured and fallback paths."""
        folder_str = self.config.templates_folder or "00-09_Meta/02_Template"
        candidates = [
            self.config.root_path / folder_str,
            self.config.root_path / "01-09_Risorse_Di_Sistema" / "01_Templates",
            self.config.root_path / "00-09_Meta" / "02_Template",
            self.config.root_path / "Templates",
            self.config.root_path / "_templates",
        ]
        for c in candidates:
            if c.is_dir():
                return c
        return self.config.root_path / folder_str

    def list_templates(self) -> List[str]:
        """Return sorted list of template filenames found in the templates directory."""
        tmpl_dir = self.get_templates_folder()
        if not tmpl_dir or not tmpl_dir.is_dir():
            return []
        return sorted([p.name for p in tmpl_dir.glob("*.md") if not p.name.startswith(".")])

    def find_template(self, template_name_or_tipo: Optional[str]) -> Optional[Path]:
        """Attempt to locate a template by name, tipo, or path, returning None if not found."""
        if template_name_or_tipo is None or not template_name_or_tipo.strip():
            return None

        target = template_name_or_tipo.strip()

        # Check explicit path
        p_explicit = Path(target)
        if p_explicit.is_file():
            return p_explicit.resolve()
        p_vault_explicit = (self.config.root_path / p_explicit).resolve()
        if p_vault_explicit.is_file():
            return p_vault_explicit

        tmpl_dir = self.get_templates_folder()
        if not tmpl_dir or not tmpl_dir.is_dir():
            return None

        # Check exact filename / with extension / with Template_ prefix
        candidates = [
            tmpl_dir / target,
            tmpl_dir / f"{target}.md",
            tmpl_dir / f"Template_{target}.md",
        ]
        for c in candidates:
            if c.is_file():
                return c

        # Case-insensitive stem matching
        target_lower = target.lower()
        if target_lower.endswith(".md"):
            target_lower = target_lower[:-3]

        for p in tmpl_dir.glob("*.md"):
            p_stem_lower = p.stem.lower()
            if (
                p_stem_lower == target_lower
                or p_stem_lower == f"template_{target_lower}"
                or p.name.lower() == f"{target_lower}.md"
            ):
                return p

        return None

    def resolve_template_path(self, template_name_or_tipo: Optional[str]) -> Optional[Path]:
        """Resolve a template name, tipo, or path, raising TemplateError if not found.

        Args:
            template_name_or_tipo: Template name, tipo, or explicit path. If None, returns None.

        Returns:
            Resolved Path of the template file, or None if none requested.

        Raises:
            TemplateError: If an explicit template name was specified but cannot be found.
        """
        if template_name_or_tipo is None or not template_name_or_tipo.strip():
            return None

        found = self.find_template(template_name_or_tipo)
        if found is not None:
            return found

        tmpl_dir = self.get_templates_folder()
        raise TemplateError(
            f"Template '{template_name_or_tipo.strip()}' not found in '{tmpl_dir}'. "
            f"Available templates: {', '.join(self.list_templates()) or '(None)'}"
        )

    def get_default_template(self, tipo: str) -> str:
        """Generate built-in standard template content conforming to Vault governance rules."""
        norm_tipo = tipo.strip().capitalize()

        if norm_tipo == "Appunto":
            return (
                "---\n"
                "tipo: Appunto\n"
                "tags: []\n"
                "---\n\n"
                "# {{title}}\n\n"
                "## Note e Concetti Chiave\n\n"
                "## Riferimenti e Collegamenti\n"
            )

        if norm_tipo == "Contatto":
            return (
                "---\n"
                "tipo: Contatto\n"
                'azienda: ""\n'
                'ruolo: ""\n'
                "rapporto: da_contattare\n"
                "tags: []\n"
                "---\n\n"
                "# {{title}}\n\n"
                "## Informazioni di Contatto\n"
                "- **Email:** \n"
                "- **LinkedIn:** \n"
                "- **Telefono:** \n\n"
                "## Storico Conversazioni\n"
            )

        if norm_tipo == "Progetto":
            return (
                "---\n"
                "tipo: Progetto\n"
                "priorità: media\n"
                "stato: attivo\n"
                'scadenza: ""\n'
                "tags: []\n"
                "---\n\n"
                "# {{title}}\n\n"
                "## Obiettivi e Deliverable\n\n"
                "## Task / Azioni da Fare\n"
                "- [ ] \n\n"
                "## Note e Risorse Collegate\n"
            )

        if norm_tipo == "Risorsa":
            return (
                "---\n"
                "tipo: Risorsa\n"
                "formato: libro\n"
                'autore: ""\n'
                "valutazione: 0\n"
                "stato: da_iniziare\n"
                "tags: []\n"
                "---\n\n"
                "# {{title}}\n\n"
                "## Sintesi ed Estratto\n\n"
                "## Note e Citazioni\n"
            )

        if norm_tipo == "Indice":
            return "---\ntipo: Indice\ntags: []\n---\n\n# {{title}}\n\n## Sezioni\n"

        if norm_tipo == "Sistema":
            return "---\ntipo: Sistema\ntags: []\n---\n\n# {{title}}\n\n## Descrizione\n\n## Specifiche Tecniche\n"

        return f"---\ntipo: {tipo}\ntags: []\n---\n\n# {{{{title}}}}\n"

    def render_template(
        self,
        raw_content: str,
        title: str,
        stem: str,
        tipo: str,
        tags: Optional[List[str]] = None,
        extra_vars: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Interpolate variables and enforce strictly valid frontmatter schema.

        Supported variables:
            {{title}}, {{stem}}, {{tipo}}, {{type}}, {{date}}, {{time}}, {{datetime}}
            and any keys passed in extra_vars.

        Args:
            raw_content: Raw template Markdown content.
            title: Human-readable note title.
            stem: Normalized filename stem.
            tipo: Note classification type.
            tags: List of validated taxonomy tags.
            extra_vars: Optional dictionary of additional template variables.

        Returns:
            Rendered Markdown text with frontmatter and body.
        """
        now = datetime.now()
        context: Dict[str, str] = {
            "title": title,
            "stem": stem,
            "tipo": tipo,
            "type": tipo,
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M"),
            "datetime": now.isoformat(timespec="seconds"),
        }

        if extra_vars:
            for k, v in extra_vars.items():
                context[k] = str(v)

        # Interpolate variables: {{var}} or {{ var }}
        def repl(match: re.Match) -> str:
            var_name = match.group(1).strip()
            for k, v in context.items():
                if k.lower() == var_name.lower():
                    return v
            return match.group(0)

        interpolated = re.sub(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}", repl, raw_content)

        # Parse document to normalize and enforce frontmatter
        doc = MarkdownDocument.from_content(interpolated)
        doc.tipo = tipo

        if tags is not None:
            doc.set_frontmatter_field("tags", list(tags))
        else:
            # Clean up dummy tags from template if present
            existing_tags = doc.tags
            if tipo.lower() != "sistema":
                existing_tags = [t for t in existing_tags if t.lower() != "sistema"]
            doc.set_frontmatter_field("tags", existing_tags)

        return doc.to_content()
