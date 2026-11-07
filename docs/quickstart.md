# Prontuario Operativo Rapido (`docs/quickstart.md`)

Guida rapida per l'installazione, configurazione iniziale e le routine operative quotidiane di **VaultKeeper** (`vk`).

---

## 1. Installazione e Requisiti

### Requisiti di Sistema
- **Python:** >= 3.10 (collaudato fino a Python 3.14).
- **Sistemi Operativi:** Linux (Ubuntu Server), macOS, Windows (PowerShell / Termius).
- **Dipendenze Chiave:** `proteus-config`, `pyyaml`.

### Installazione da PyPI
```bash
pip install obsidian-vaultkeeper
```

### Installazione in Ambiente di Sviluppo
```bash
git clone git@github.com:lucadileo9/obsidian-vaultkeeper.git
cd obsidian-vaultkeeper
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Verificare l'installazione visualizzando la versione:
```bash
vk --version
# Output: vk 0.1.0
```

---

## 2. Inizializzazione del Vault (`vk init`)

Per adottare VaultKeeper su un nuovo Second Brain o cartella documentale:

```bash
# Eseguito direttamente all'interno della radice del Vault:
vk init

# Oppure specificando la cartella target:
vk init --target /srv/storage/Vault
```

Questo comando genera il file di configurazione [vault.toml](file:///home/lucadileo9/scripts/obsidian-vaultkeeper/vault.toml.example) con le convenzioni predefinite (stile `Title_Case`, prefissi Johnny.Decimal, MOC contestuali e tassonomia protetta).

---

## 3. Routine Operative Standard

### Routine Diagnostica Settimanale (Audit)
Per verificare la salute complessiva del Vault, individuare link rotti, note senza tipo o allegati orfani:
```bash
vk audit --root /srv/storage/Vault
```

Se si desidera esportare il report diagnostico in formato JSON o Markdown per reportistica periodica:
```bash
vk audit --json audit_results.json --report-md audit_report.md
```

### Routine di Verifica Collegamenti (`check-links`)
Scansione focalizzata per individuare wikilink (`[[...]]`) ed embed multimediali (`![[...] ]`) non risolti:
```bash
# Scansione su tutto il vault
vk check-links

# Scansione circoscritta a una cartella specifica
vk check-links --target /srv/storage/Vault/10-19_Progetti
```

### Routine di Manutenzione Allegati (`clean-attachments`)
Per individuare e rimuovere file multimediali non citati da alcuna nota:

```bash
# Fase 1: Simulazione sicura (mostra cosa verrebbe spostato senza toccare il disco)
vk clean-attachments --dry-run

# Fase 2: Esecuzione soft-delete (sposta i file orfani nella cartella .trash del Vault)
vk clean-attachments

# Opzionale: Eliminazione definitiva e irreversibile
vk clean-attachments --hard-delete
```

### Routine di Normalizzazione Nomi (`normalize-names`)
Rinomina file e cartelle secondo lo standard impostato (`Title_Case`) e sincronizza atomicamente tutti i wikilink in ingresso:

```bash
# Simulazione preventiva
vk normalize-names --target /srv/storage/Vault/20-29_Aree --dry-run

# Applicazione effettiva
vk normalize-names --target /srv/storage/Vault/20-29_Aree
```

### Routine di Generazione MOC (`generate-indices`)
Crea o aggiorna le note indice per ciascuna cartella, catalogando sottocartelle, note markdown con sommario e documenti non-markdown (`.pdf`, `.docx`, `.xlsx`):

```bash
# Per una sola cartella
vk generate-indices --target /srv/storage/Vault/10-19_Progetti

# Ricorsivamente per l'intero albero del Vault
vk generate-indices --all
```

---

## 4. Codici di Uscita Semantici (POSIX Exit Codes)

Tutti i comandi CLI restituiscono codici conformi per integrazione con cron job, script bash o pipeline CI/CD:

| Codice | Significato | Comportamento Tipico |
| :---: | :--- | :--- |
| `0` | **Successo Totale (`EXIT_SUCCESS`)** | L'operazione e' terminata regolarmente e non sono state riscontrate violazioni (Vault pulito, 0 link rotti). |
| `1` | **Errore di Sistema (`EXIT_ERROR`)** | Parametri errati, percorso inesistente, eccezione non gestita. |
| `2` | **Criticita' Rilevate (`EXIT_ISSUES_FOUND`)** | L'audit ha rilevato violazioni o `vk check-links` ha trovato collegamenti spezzati. Permette a cron job di allertare l'amministratore. |

---

## 5. Gestione del Logging su File

Per conservare uno storico delle operazioni senza interferire con l'output colorato del terminale:

```bash
vk audit --log-file /srv/storage/Vault/01-09_Risorse_Di_Sistema/Logs/audit.log
```

Il gestore interno di logging rimuove automaticamente tutte le sequenze di escape ANSI dal file, garantendo un log in puro testo chiaro e indicizzabile.
