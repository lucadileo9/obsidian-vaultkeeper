# Guida alla Core API Python e Integrazione MCP (`docs/python-api.md`)

Questa guida illustra l'utilizzo programmatico della libreria `vaultkeeper` in script Python autonomi e l'esposizione degli strumenti tramite server **FastMCP** (Model Context Protocol) per agenti AI.

---

## 1. La Facciata Principale (`vaultkeeper.Vault`)

L'intera interazione con il Vault avviene tramite la classe `Vault`:

```python
from pathlib import Path
from vaultkeeper import Vault

# Inizializzazione automatica (cerca vault.toml nella radice o fallback globale)
vault = Vault("/srv/storage/Vault")

# Oppure specificando un file di configurazione personalizzato:
vault = Vault(
    root_path="/srv/storage/Vault",
    config_file="/home/lucadileo9/.config/vaultkeeper/custom.toml"
)
```

---

## 2. Metodi della Classe `Vault`

### Diagnostica e Audit
```python
# Esecuzione audit completo su tutte le 5 fasi:
report = vault.audit()
print(f"Health Score: {report.health_score} / 100.0")
print(f"Totale criticita': {report.total_issues}")

# Esportazione del report in dizionario serializzabile JSON:
report_dict = report.to_dict()

# Esecuzione selettiva di specifiche fasi (es. solo Link e Frontmatter):
report_sub = vault.audit(phases=[3, 5])
```

### Controllo Collegamenti e Collisioni
```python
# Scansione di tutti i collegamenti rotti:
broken_links = vault.check_links()
for b in broken_links:
    tipo = "Embed immagine" if b.is_media_embed() else "Wikilink"
    print(f"{tipo} rotto: [[{b.clean_target}]] in {b.source_file.name}:{b.line_number}")

# Rilevamento collisioni di stem omonimi:
collisions = vault.stem_collisions()
for stem, paths in collisions.items():
    print(f"Collisione per '{stem}': trovato in {len(paths)} cartelle distinte.")
```

### Pulizia e Manutenzione Allegati
```python
# Trova file multimediali orfani:
orphans = vault.find_orphans()
for o in orphans:
    print(f"File orfano: {o.rel_path} ({o.size_bytes} byte)")

# Esegui soft-delete verso la cartella .trash:
results = vault.clean_attachments(dry_run=False, hard_delete=False)

# Esegui eliminazione definitiva permanente:
results = vault.clean_attachments(dry_run=False, hard_delete=True)
```

### Normalizzazione Nomi e Sincronizzazione Wikilink
```python
# Normalizza tutti i file e aggiorna atomicamente i wikilink in ingresso:
renamed = vault.normalize_names(dry_run=False)
for old_path, new_path, updated_links in renamed:
    print(f"Rinominato: {old_path.name} -> {new_path.name} ({updated_links} collegamenti aggiornati)")
```

### Generazione Mappe di Contenuto (MOC)
```python
# Genera indici per tutte le cartelle dell'albero:
indices = vault.generate_indices(recursive=True, dry_run=False)
for idx_path, was_modified in indices:
    stato = "Creato/Modificato" if was_modified else "Invariato"
    print(f"{idx_path.name}: {stato}")
```

### Manipolazione Metadati Frontmatter
```python
# Lettura strutturata di una nota:
nota = vault.get_note("/srv/storage/Vault/10-19_Progetti/Mio_Progetto.md")
if nota.frontmatter:
    print(f"Tipo: {nota.frontmatter.tipo}")
    print(f"Tags: {nota.frontmatter.tags}")

# Aggiornamento del campo tipo:
vault.set_frontmatter_type("/srv/storage/Vault/10-19_Progetti/Mio_Progetto.md", "Progetto")

# Aggiunta di tag nel frontmatter:
vault.add_frontmatter_tags(
    "/srv/storage/Vault/10-19_Progetti/Mio_Progetto.md",
    tags=["area/lavoro", "stato/attivo"],
    overwrite=False
)
```

---

## 3. Server MCP (Model Context Protocol) per Agenti AI

L'assoluta purezza computazionale di `vaultkeeper` consente di realizzare in poche righe un server **FastMCP** per integrare il Second Brain con Claude Desktop, Google Gemini o Cursor:

```python
"""Server MCP per l'orchestrazione autonoma di VaultKeeper."""

from pathlib import Path
from typing import Any, Dict, List
from mcp.server.fastmcp import FastMCP
from vaultkeeper import Vault

mcp = FastMCP("VaultKeeper-Server")

VAULT_DEFAULT_PATH = "/srv/storage/Vault"

@mcp.tool()
def audit_vault(vault_path: str = VAULT_DEFAULT_PATH) -> Dict[str, Any]:
    """Esegue l'audit a 5 fasi del Vault e restituisce Health Score e criticita'."""
    v = Vault(vault_path)
    return v.audit().to_dict()

@mcp.tool()
def get_broken_links(vault_path: str = VAULT_DEFAULT_PATH) -> List[Dict[str, Any]]:
    """Restituisce l'elenco dei collegamenti rotti o allegati mancanti nel Vault."""
    v = Vault(vault_path)
    return [
        {
            "source": str(b.source_file),
            "line": b.line_number,
            "target": b.clean_target,
            "is_media": b.is_media_embed(),
        }
        for b in v.check_links()
    ]

@mcp.tool()
def generate_indices(vault_path: str = VAULT_DEFAULT_PATH, recursive: bool = True) -> List[str]:
    """Genera o aggiorna le note indice MOC per le cartelle del Vault."""
    v = Vault(vault_path)
    results = v.generate_indices(recursive=recursive, dry_run=False)
    return [str(path) for path, modified in results if modified]

if __name__ == "__main__":
    mcp.run()
```
