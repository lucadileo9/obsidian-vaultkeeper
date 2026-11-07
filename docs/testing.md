# Protocollo di Test, Collaudo e Qualità (`docs/testing.md`)

Questo documento descrive la suite di test automatizzati, le pratiche di isolamento e gli standard di qualità per lo sviluppo di **VaultKeeper**.

---

## 1. Struttura della Suite di Test (`tests/`)

La suite comprende 53 test unitari ed End-to-End con una copertura di codice superiore all'83%:

```text
tests/
├── conftest.py             # Fixture pytest: generazione di Vault fittizi temporanei isolati
├── test_config.py          # Test caricamento configurazione con proteus-config
├── test_helpers.py         # Test formattazione byte, calcolo hash SHA256 e troncamento testo
├── test_naming.py          # Test strategie di naming (Title_Case, kebab, snake) e sync wikilink
├── test_frontmatter.py     # Test round-trip YAML, protezione codice C e colori HEX
├── test_links.py           # Test lookup O(1), risoluzione shortest-path e rilevamento link rotti
├── test_attachments.py    # Test individuazione allegati orfani, file pesanti e soft-delete
├── test_indices.py        # Test naming contestuale MOC e generazione sezioni
├── test_audit.py          # Test diagnostica a 5 fasi e calcolo Vault Health Score
├── test_vault.py          # Test della facciata Vault (API Python pura)
├── test_cli.py            # Test di integrazione per il comando 'vk' e tutti i sottocomandi
└── test_e2e_vault.py      # Ciclo di vita End-to-End: vault sporco -> audit -> remediation -> 100/100
```

---

## 2. Principio di Isolamento Assoluto (Fixtures)

Nessun test tocca o legge mai il Vault di produzione (`/srv/storage/Vault`):
- Tutte le fixture in `conftest.py` creano cartelle temporanee tramite `tempfile.TemporaryDirectory()`.
- Al termine dell'esecuzione del test, la cartella temporanea viene distrutta automaticamente dal sistema operativo.
- La fixture `mock_vault` crea una gerarchia realistica con tassonomia ufficiale (`00_Tassonomia_Tag.md`), note collegate, wikilink rotti intenzionali ed allegati orfani per verificare con precisione il comportamento del software.

---

## 3. Esecuzione dei Test

### Esecuzione Rapida
```bash
pytest tests/
```

### Esecuzione con Report di Copertura (Coverage)
```bash
pytest --cov=vaultkeeper --cov-report=term-missing tests/
```

### Verifica di Stile e Formattazione con Ruff
```bash
# Controllo linting
ruff check src/ tests/

# Autofix per problemi risolvibili automaticamente
ruff check --fix src/ tests/
```

---

## 4. Test End-to-End di Ciclo di Vita (`test_e2e_vault.py`)

Il test `test_full_vault_lifecycle_and_remediation` convalida l'intero workflow sistemico:
1. Istanzia un Vault fittizio grezzo contenente:
   - File con nomi non conformi (`bad name.md`).
   - Nota priva di intestazione frontmatter.
   - Collegamento spezzato (`[[Non_Esiste]]`).
   - File immagine orfano (`Orphan_File.png`).
2. Esegue il primo audit verificando che lo score sia strettamente $< 100.0$ e che vengano segnalati errori nelle fasi 2, 3 e 5.
3. Esegue la pipeline di remediation (`normalize_names`, `set_frontmatter_type`, `add_frontmatter_tags`, pulizia orfani e `generate_indices`).
4. Esegue il secondo audit verificando che lo score finale raggiunga esattamente **100.0 / 100.0** e che `report.is_clean()` ritorni `True`.

---

## 5. Convenzioni per Nuovi Contributi

Qualsiasi modifica o estensione della libreria deve rispettare i seguenti requisiti prima del merge:
1. Tutti i 53 test preesistenti devono continuare a passare con successo (`0 failures`).
2. Eventuali nuove funzionalità devono essere coperte da test unitari dedicati in `tests/`.
3. Il codice deve essere conforme al linter `ruff` con zero errori o warning.
4. I commit devono seguire rigorosamente lo standard **Conventional Commits** (`feat:`, `fix:`, `test:`, `docs:`, `chore:`).
