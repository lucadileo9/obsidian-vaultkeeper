# VaultKeeper (`obsidian-vaultkeeper` / `vk`)

> Universal Second Brain governance engine, link validator and maintenance toolkit for Obsidian and document vaults.

[![CI](https://img.shields.io/badge/tests-53%20passed-brightgreen.svg)]()
[![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13%20%7C%203.14-blue.svg)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## Panoramica

`vaultkeeper` (distribuito su PyPI come `obsidian-vaultkeeper` con comando CLI `vk`) e' una libreria modulare e motore di governance universale per Second Brain personali, archivi documentali (Google Drive, Microsoft SharePoint, OneDrive) e server MCP per agenti AI autonomi.

Sviluppato per superare le limitazioni di script procedurali isolati, garantisce una separazione architetturale rigida tra:
1. **Core API Computazionale Pura (`vaultkeeper.core`):** Nessun effetto collaterale, zero chiamate a `print()` o `sys.exit()`, ritorno esclusivo di modelli di dominio tipizzati (`dataclass`) o sollevamento di eccezioni dedicate (`VaultKeeperError`).
2. **Motore di Configurazione Dinamico (`vaultkeeper.config`):** Integrazione nativa con la libreria PyPI `proteus-config` per la gestione gerarchica del file `vault.toml`.
3. **Livello di Presentazione CLI (`vaultkeeper.cli`):** Sottocomandi espliciti (`vk audit`, `vk check-links`, `vk clean-attachments`, `vk normalize-names`, `vk generate-indices`, `vk frontmatter`, `vk disambiguate`, `vk init`), log formattati a colori su terminale ANSI e rimozione automatica dei codici ANSI su file di log.

---

## Installazione

```bash
pip install obsidian-vaultkeeper
```

Per l'ambiente di sviluppo e collaudo:
```bash
git clone https://github.com/lucadileo9/obsidian-vaultkeeper.git
cd obsidian-vaultkeeper
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

---

## Utilizzo da Riga di Comando (`vk`)

La CLI espone comandi autoesplicativi, flag per simulazione non distruttiva (`--dry-run`), formattazione log su file (`--log-file`) e codici di uscita semantici POSIX (`0` = Successo, `1` = Errore, `2` = Rilevate criticita'/link rotti):

```text
vk [-h] [-v] [-q] [--log-file LOG_FILE] [--root ROOT] [--config CONFIG] [--version] <command>
```

### Comandi Principali

| Comando | Descrizione |
| :--- | :--- |
| `vk init [--target <dir>]` | Genera un file `vault.toml` di default pronto all'uso. |
| `vk audit [--step 1..5] [--json out.json] [--report-md out.md]` | Diagnostica unificata a 5 fasi con calcolo del Vault Health Score (0-100). |
| `vk check-links [--target <path>]` | Scansione O(1) di wikilink spezzati ed embed multimediali mancanti. |
| `vk clean-attachments [--dry-run] [--hard-delete]` | Individuazione e spostamento nel cestino `.trash` di file multimediali orfani. |
| `vk normalize-names [--dry-run] [--target <path>]` | Normalizzazione di file e cartelle (`Title_Case`, `kebab-case`, `snake_case`) e sincronizzazione atomica dei wikilink correlati. |
| `vk generate-indices [--all] [--dry-run] [--target <path>]` | Generazione/aggiornamento di mappe di contenuto (MOC) con naming contestuale anti-collisione (`00_Indice_<Cartella>.md`). |
| `vk frontmatter set-type --target <file> --type <nome>` | Impostazione o aggiornamento sicuro del campo `tipo` YAML. |
| `vk frontmatter add-tags --target <file> --tags <t1> <t2>` | Iniezione o aggiornamento di tag YAML senza alterare altri metadati. |
| `vk frontmatter sanitize-tags [--dry-run]` | Linter dei tag rispetto alla tassonomia controllata e mapping di sinonimi. |
| `vk disambiguate [--target <path>]` | Rilevamento di collisioni di stem omonimi tra cartelle distinte. |

---

## Configurazione (`vault.toml`)

Un file `vault.toml` posto nella radice del Vault (o in `~/.config/vaultkeeper/config.toml`) governa le policy di convalida:

```toml
[vault]
root_path = "/srv/storage/Vault"
allowed_extensions = [".md", ".pdf", ".png", ".jpg", ".jpeg", ".svg", ".docx", ".xlsx", ".pptx"]
ignored_folders = [".obsidian", ".trash", ".git", ".stversions", ".deleted", "node_modules", ".venv"]
max_path_length = 240

[naming]
style = "Title_Case"                         # "Title_Case", "kebab-case", "snake_case", "none"
disallowed_chars = "[\'\\":?*!&|<>,\\\\\\\\()]"
acronyms = ["AI", "API", "AWS", "BCG", "CRM", "HPC", "IT", "JEMORE", "MECE", "SQL", "UX", "MOC", "PKM"]
preserve_prefix_pattern = "^[0-9]{2}(-[0-9]{2})?_"

[frontmatter]
type_field = "tipo"
allowed_types = ["Appunto", "Contatto", "Progetto", "Risorsa", "Indice", "Sistema"]
required_fields = ["tipo", "tags"]

[tags]
taxonomy_file = "00_Tassonomia_Tag.md"
strict_taxonomy = true
protect_c_directives = true                  # Previene falsi positivi per #include e #define
protect_hex_colors = true                    # Previene falsi positivi per codici colore (#FFFFFF)
tag_replacements = { "appunti" = "tipo/appunto", "risorse" = "tipo/risorsa" }

[attachments]
folder_names = ["_attachments", "attachments", "assets", "Slide", "media"]
heavy_file_threshold_mb = 50
trash_folder = ".trash"

[indices]
naming_pattern = "contextual"                # "contextual" (00_Indice_<folder>.md), "static" (00_Indice.md), "readme" (README.md)
prefix = "00_"
summary_max_chars = 250
include_non_md = true
```

### Risoluzione delle Collisioni per gli Indici

La modalita' `naming_pattern = "contextual"` genera file nel formato `00_Indice_<Nome_Cartella>.md` (es. `00_Indice_Progetti.md` per la cartella `10-19_Progetti`). Questo elimina le ambiguità nel Quick Switcher di Obsidian (`Ctrl + O`) preservando al contempo l'ordinamento naturale in cima alla cartella grazie al prefisso `00_`.

---

## Utilizzo come Libreria Python

```python
from vaultkeeper import Vault

# Inizializzazione della facciata
vault = Vault("/percorso/del/vault")

# 1. Diagnostica a 5 fasi
report = vault.audit()
print(f"Health Score: {report.health_score} / 100.0 (Problemi: {report.total_issues})")

# 2. Controllo collegamenti rotti
broken = vault.check_links()
for link in broken:
    print(f"Link rotto: [[{link.clean_target}]] in {link.source_file.name}:{link.line_number}")

# 3. Pulizia allegati orfani
cleaned = vault.clean_attachments(dry_run=False)
print(f"Spostati nel cestino {len(cleaned)} file orfani.")

# 4. Normalizzazione nomi e aggiornamento sincronizzato dei wikilink
renamed = vault.normalize_names(dry_run=False)
for old_p, new_p, links_updated in renamed:
    print(f"Rinominato {old_p.name} -> {new_p.name} (Aggiornati {links_updated} collegamenti)")

# 5. Generazione automatica MOC per tutte le cartelle
indices = vault.generate_indices(recursive=True)
print(f"Generate {len(indices)} note indice MOC.")
```

---

## Integrazione con Server MCP (Model Context Protocol)

Grazie alla Core API pura, esporre gli strumenti di VaultKeeper ad agenti AI tramite FastMCP richiede pochissime righe:

```python
from mcp.server.fastmcp import FastMCP
from vaultkeeper import Vault

mcp = FastMCP("VaultKeeper-Server")

@mcp.tool()
def audit_vault(vault_path: str = "/srv/storage/Vault") -> dict:
    """Esegue l'audit completo di integrità del Vault e restituisce il report strutturato."""
    v = Vault(vault_path)
    return v.audit().to_dict()

@mcp.tool()
def get_broken_links(vault_path: str = "/srv/storage/Vault") -> list:
    """Restituisce l'elenco dei collegamenti spezzati o allegati mancanti."""
    v = Vault(vault_path)
    return [b.__dict__ for b in v.check_links()]
```

---

## Suite di Test e Qualita'

Il progetto include 53 test unitari ed End-to-End con oltre l'83% di copertura del codice:

```bash
pytest --cov=vaultkeeper --cov-report=term-missing tests/
ruff check src/ tests/
```

---

## Autore e Licenza

- **Autore:** Luca Di Leo (<lucadileo70@gmail.com>)
- **Licenza:** MIT License (consultare il file `LICENSE` per i dettagli).
