# Obsidian VaultKeeper (`vk`)

> Motore universale di governance, refactoring atomico, diagnostica e manutenzione per Second Brain Obsidian e archivi documentali.

[![CI](https://github.com/lucadileo9/obsidian-vaultkeeper/actions/workflows/ci.yml/badge.svg)](https://github.com/lucadileo9/obsidian-vaultkeeper/actions/workflows/ci.yml)
[![Coverage](https://img.shields.io/badge/coverage-90%25-brightgreen.svg)]()
[![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13%20%7C%203.14-blue.svg)]()
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)

---

## Panoramica

**`obsidian-vaultkeeper`** (distribuito tramite il binario da riga di comando **`vk`** e come libreria Python `vaultkeeper`) è un sistema di livello enterprise progettato per presidiare, normalizzare e manutenere archivi di appunti Markdown complessi (oltre 3.900 note su architettura Johnny.Decimal).

Il sistema è ingegnerizzato secondo un'**architettura a doppia testa**:
1. **SDK Python Programmatico ([`Vault`](docs/architecture/facade.md))**: API orientata agli oggetti, priva di effetti collaterali a terminale (zero `print` o `sys.exit`), che scambia modelli di dominio immutabili ed è nativamente predisposta per script di automazione e server MCP per agenti AI autonomi.
2. **Command Line Interface ([`vk`](docs/cli/overview.md))**: Interfaccia moderna a 20 comandi, arricchita con rendering `Rich`, simulazioni di sicurezza pre-volo (`--dry-run`), formati serializzabili (`--format json|yaml|csv`) e codici di ritorno semantici POSIX (`ExitCode`).

Tutte le operazioni mutative sono incapsulate in un **Transaction Journal atomico con hashing crittografico SHA-256 e rollback LIFO**: qualsiasi creazione, rinomina, spostamento o cancellazione può essere annullata all'istante tramite `vk undo`.

---

## Installazione

### Tramite Pip (Ambiente Virtuale)
```bash
pip install obsidian-vaultkeeper
```

### Installazione per Sviluppo e Contributi
```bash
git clone https://github.com/lucadileo9/obsidian-vaultkeeper.git
cd obsidian-vaultkeeper
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

---

## Primi Passi (Quickstart)

### 1. Inizializzare la Configurazione del Vault
```bash
vk init --target /srv/storage/Vault
```
Genera il file guida `vault.toml` con le convenzioni di denominazione (`Title_Case`), i tag ammessi, le estensioni consentite e le soglie di archiviazione.

### 2. Eseguire l'Audit Diagnostico a 5 Fasi
```bash
vk audit
```
Verifica filesystem, denominazione, conformità frontmatter YAML, tassonomia controllata dei tag e integrità dei wikilink, calcolando il **Vault Health Score** (da 0.0 a 100.0).

### 3. Creare una Nuova Nota Standardizzata
```bash
vk create "Architettura a Microservizi" --type Appunto --tags "tech/architettura,tech/cloud"
```
Applica automaticamente l'auto-routing Johnny.Decimal verso la cartella corretta (`20-29_Istruzione/`), inietta le variabili nel template e aggiorna il MOC `00_Indice.md`.

### 4. Rinominare con Refactoring Globale dei Backlink
```bash
vk rename 10-19_Progetti/vecchio_progetto.md Progetto_Varys
```
Rinomina il file e aggiorna simultaneamente tutti i collegamenti `[[...]]` che puntavano al vecchio nome all'interno dell'intero Vault.

### 5. Annullare un'Operazione Involontaria
```bash
vk undo
```
Esegue un controllo di sicurezza crittografico SHA-256 (rifiuta il rollback se i file sono stati modificati nel frattempo da terzi) e ripristina lo stato precedente in ordine inverso.

---

## Tabella Sinottica dei 20 Comandi CLI

Per la consultazione dettagliata di argomenti, opzioni ed esempi d'uso per ciascun comando, consultare il [**Manuale di Riferimento dei Comandi CLI**](docs/cli/commands_reference.md).

| Comando | Sintassi di Esempio | Descrizione Operativa | Reversibile con `undo` |
| :--- | :--- | :--- | :---: |
| **`init`** | `vk init [--force]` | Genera il file di configurazione predefinito `vault.toml`. | No |
| **`audit`** | `vk audit [--step 1..5] [--json out.json]` | Diagnostica a 5 fasi con calcolo del Vault Health Score. | No (Read-Only) |
| **`check-links`** | `vk check-links [--target <path>]` | Rileva wikilink rotti ed embed multimediali orfani. | No (Read-Only) |
| **`clean-attachments`** | `vk clean-attachments [--dry-run]` | Bonifica file orfani tramite soft-delete reversibile in `.trash/`. | **Sì** |
| **`normalize-names`** | `vk normalize-names [--dry-run]` | Converte in `Title_Case` e riscrive contestualmente i backlink. | **Sì** |
| **`generate-indices`** | `vk generate-indices [--all] [--dry-run]` | Genera o aggiorna i file MOC `00_Indice.md` di cartella. | No (Idempotente) |
| **`frontmatter`** | `vk frontmatter set-type --target n.md --type Appunto` | Ispeziona o modifica metadati YAML (`tipo`, tag). | **Sì** |
| **`disambiguate`** | `vk disambiguate [--target <dir>]` | Rileva collisioni di stem omonimi tra cartelle diverse. | No (Read-Only) |
| **`history`** | `vk history [--limit 20] [--format json]` | Mostra lo storico delle transazioni atomiche del Journal. | No (Read-Only) |
| **`undo`** | `vk undo [--tx <id>] [--dry-run]` | Ripristina lo stato del filesystem precedente con verifica SHA-256. | **Sì** (Rollback) |
| **`rename`** | `vk rename vecchio.md Nuovo.md` | Rinomina una nota con sincronizzazione globale di backlink e MOC. | **Sì** |
| **`move`** | `vk move nota.md 10-19_Progetti/` | Sposta file o cartelle aggiornando entrambi i MOC di area. | **Sì** |
| **`archive`** | `vk archive Progetto_X/ [--no-tombstone]` | Trasferisce in cold storage e deposita scheda tombstone. | **Sì** |
| **`offload`** | `vk offload [target] [--dry-run]` | Sposta allegati pesanti (>50MB) in cold storage rimpiazzando i link. | **Sì** |
| **`tags`** | `vk tags add tech/rust [--section "Tecnologia"]` | Gestisce il vocabolario controllato `00_Tassonomia_Tag.md`. | **Sì** |
| **`config`** | `vk config set naming_style Title_Case` | Ispeziona o modifica impostazioni a caldo in `vault.toml`. | **Sì** |
| **`search`** | `vk search "query" [--tag t] [--type Appunto]` | Ricerca full-text e filtri combinatori multi-criterio. | No (Read-Only) |
| **`graph-health`** | `vk graph-health [--format md]` | Analisi topologica del grafo (top hubs, dead-ends, orfani). | No (Read-Only) |
| **`map`** | `vk map [--output Mappa.md] [--format json]` | Cartografia strutturale Johnny.Decimal e volumi del Vault. | No (Read-Only) |
| **`create`** | `vk create "Titolo" --type Appunto [--tags ...]` | Creazione standardizzata con auto-routing, template e MOC. | **Sì** |

---

## Utilizzo come Libreria Python (SDK)

La classe Facade [`Vault`](docs/architecture/facade.md) espone un'interfaccia unificata per script di automazione o agenti intelligenti:

```python
from vaultkeeper import Vault

# Inizializzazione della Facade
vault = Vault(root_path="/srv/storage/Vault")

# 1. Diagnostica e referto di salute
report = vault.audit()
print(f"Health Score: {report.health_score}/100.0 (Problemi: {report.total_issues})")

# 2. Creazione standardizzata con auto-routing
result = vault.create(
    title="Strategie di Ottimizzazione Memoria",
    tipo="Appunto",
    tags=["tech/python", "architettura/performance"],
)
print(f"Nota creata in: {result.file_path} (Transazione: {result.tx_id})")

# 3. Rinomina sicura con refactoring globale dei wikilink
rename_res = vault.rename(
    old_path="20-29_Istruzione/Informatica/vecchio_appunto.md",
    new_name="Nuovo_Appunto",
)
print(f"Wikilink aggiornati: {rename_res.updated_links_count}")

# 4. Rollback immediato in caso di errore
undo_res = vault.undo()
print(f"Rollback completato: {undo_res.reverted_actions} azioni ripristinate")
```

---

## Mappa della Documentazione Tecnica

L'intero impianto documentale è organizzato nella cartella [`docs/`](docs):

```text
docs/
├── architecture/
│   ├── facade.md              # Disamina completa della Facade (Vault), metodi e sequenze
│   ├── core_modules.md        # I 15 moduli computazionali del core: classi, funzioni, I/O
│   ├── models.md              # Catalogo esaustivo dei 23 Domain Models immutabili
│   └── transaction_journal.md # Meccanica dello stato, hashing SHA-256 e rollback LIFO
├── cli/
│   ├── overview.md            # Panoramica CLI, exit codes, opzioni globali e dry-run
│   └── commands_reference.md  # Specifiche esaustive e parametri per tutti i 20 comandi
└── testing/
    └── test_suite.md          # 153 test, copertura 90%, fixture isolate e matrici CI
```

---

## Qualità e Suite di Test

- **Test Suite**: 153 test automatizzati eseguiti in meno di 0.8s.
- **Copertura del Codice**: $\ge 90\%$ complessivo misurato con `pytest-cov`.
- **Controllo Tipi Statico**: 100% conforme a `mypy --strict` su 78 file sorgente.
- **Stile & Linting**: 100% conforme alle regole di `ruff check` e `ruff format`.
- **Sicurezza**: Zero vulnerabilità o avvisi rilevati tramite scanner AST `bandit`.

Per eseguire localmente la suite di test e le verifiche di qualità:
```bash
.venv/bin/pytest --cov=vaultkeeper --cov-report=term-missing
.venv/bin/mypy src/ tests/
.venv/bin/ruff check src/ tests/
.venv/bin/bandit -r src/ -ll
```

---

## Licenza

Questo progetto è rilasciato sotto licenza [GNU General Public License v3.0](LICENSE).
