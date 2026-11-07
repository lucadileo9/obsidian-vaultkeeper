# Specifiche Architetturali e Modelli di Dominio (`docs/architecture.md`)

Questo documento formalizza l'architettura tecnica, i modelli di dominio e i design pattern implementati in **VaultKeeper**.

---

## 1. Principi di Progettazione Fondamentali

VaultKeeper e' stato concepito secondo tre direttive inviolabili:

1. **Separazione Totale tra Computazione e Presentazione:**
   Il modulo `vaultkeeper.core` contiene logica di calcolo pura. Non invoca `print()`, non usa codici di escape ANSI a terminale e non chiama `sys.exit()`. Ogni operazione accetta oggetti `Path` o modelli di configurazione e ritorna istanze immutabili o solleva eccezioni tipizzate.
2. **Prestazioni su Volumi Elevati ($O(1)$ Lookup):**
   Nei Second Brain contenenti migliaia di note (es. oltre 4.000 file), la scansione lineare da disco per ogni singolo wikilink comporterebbe complessità computazionale $O(N \times M)$ ingestibile. VaultKeeper introduce un catalogo indicizzato in memoria (`VaultCatalog`) che riduce la risoluzione dei target a lookup con complessità media $O(1)$.
3. **Integrità Referenziale Globale nei Rename:**
   Qualsiasi ridenominazione o normalizzazione di file/cartelle esegue automaticamente la scansione e riscrittura coerente di tutti i wikilink in ingresso distribuiti nell'intero Vault.

---

## 2. Architettura a Livelli (Layered Architecture)

```text
+-----------------------------------------------------------------------+
|                       LIVELLO PRESENTAZIONE / CLI                     |
|            vaultkeeper.cli (main.py, logging.py, commands/*)           |
+-----------------------------------------------------------------------+
                                    |
                                    v
+-----------------------------------------------------------------------+
|                       LIVELLO FACCIATA (FACADE API)                   |
|                        vaultkeeper.Vault (__init__.py)                |
+-----------------------------------------------------------------------+
                                    |
        +---------------------------+---------------------------+
        v                                                       v
+-------------------------------+               +-------------------------------+
|     CONFIGURAZIONE (PROTEUS)  |               |       MOTORE CORE COMPUTAZ.   |
|   vaultkeeper.config          |               |   vaultkeeper.core.*          |
|   (vault.toml, proteus-config)|               |   (traversal, links, naming,  |
+-------------------------------+               |    frontmatter, indices, ...) |
                                                +-------------------------------+
                                                                |
                                                                v
                                                +-------------------------------+
                                                |     MODELLI DI DOMINIO        |
                                                |   vaultkeeper.models          |
                                                |   vaultkeeper.exceptions      |
                                                +-------------------------------+
```

---

## 3. Modelli di Dominio (`models.py`)

Tutti i dati scambiati tra le componenti sono incapsulati in `dataclass` rigorosamente tipizzate:

- **`BrokenLink`:** Rappresenta un collegamento non risolto. Conserva `source_file`, `line_number`, `raw_target`, `clean_target`, `anchor` e `alias`. Include il metodo `.is_media_embed()` per discriminare wikilink concettuali da allegati mancanti.
- **`Frontmatter`:** Rappresenta l'intestazione YAML analizzata. Conserva il testo grezzo `raw_content`, il dizionario `metadata`, il valore `tipo` e la lista `tags`. Fornisce metodi di validazione `.has_tag()` e `.is_valid_type()`.
- **`Note`:** Modello di una nota Markdown, con percorso assoluto e relativo rispetto alla radice del Vault, frontmatter opzionale, corpo del testo e dimensione in byte.
- **`OrphanAttachment`:** Rappresenta un file binario o multimediale presente sul disco non citato da alcuna nota del Vault.
- **`PhaseResult`:** Risultato diagnostico di una singola fase di audit, con elenco problemi (`issues`), avvisi (`warnings`) e metriche di riepilogo.
- **`AuditReport`:** Report complessivo delle 5 fasi, con timestamp ISO UTC, totale criticita' e punteggio di salute calcolato.
- **`VaultCatalog`:** Indice di memoria $O(1)$ contenente mappe di lookup:
  - `notes_by_stem: Dict[str, List[Path]]` (ricerca per nome nota privo di estensione)
  - `files_by_name: Set[str]` (ricerca esatta per nome file e allegati)
  - `rel_paths: Set[str]` (mappa dei percorsi relativi)
- **`VaultConfig`:** Schema tipizzato di tutte le opzioni estratte dal file `vault.toml` tramite `proteus-config`.

---

## 4. Algoritmo di Risoluzione dei Collegamenti (Shortest-Path Resolution)

Per rispecchiare con assoluta fedeltà il motore interno di Obsidian, la funzione `resolve_link_target` applica la seguente cascata decisionale:

1. **Riferimento ad Ancora Interna (`[[#Intestazione]]`):** Se il target e' vuoto o inizia con `#`, il target e' il file sorgente medesimo.
2. **Risoluzione Relativa Locale:** Cerca il file relativo alla directory della nota chiamante (`source_file.parent / target`).
3. **Risoluzione Relativa Radice:** Cerca il file relativo alla radice del Vault (`vault_root / target`).
4. **Lookup per Stem nel Catalogo:** Interroga `catalog.notes_by_stem[stem]`. Se presente una corrispondenza univoca, il collegamento e' risolto. Se sono presenti più percorsi omonimi, viene segnalata una **collisione di stem**.
5. **Lookup per Nome File Completo:** Interroga `catalog.files_by_name[filename]` (utilizzato per immagini e documenti PDF).
6. **Esito Negativo:** Se tutti i passi falliscono, il collegamento viene registrato come `BrokenLink`.

---

## 5. Rationale: Indici Contestuali vs Statici (`00_Indice_<Cartella>.md`)

Nei Second Brain organizzati con note indice tradizionali chiamate `00_Indice.md`:
- Tutte le cartelle hanno un file con il medesimo stem (`00_Indice`).
- Il Quick Switcher di Obsidian (`Ctrl + O`) mostra decine di voci identiche, costringendo l'utente a leggere con fatica il percorso secondario.
- I wikilink `[[00_Indice]]` generano ambiguita' e richiedono l'intero percorso assoluto `[[Cartella/00_Indice]]`.

### La Soluzione Adottata da VaultKeeper (`naming_pattern = "contextual"`)
1. Il nome del file indice incorpora il nome della cartella: `00_Indice_<Cartella>.md` (es. `00_Indice_Progetti.md` per la cartella `10-19_Progetti`).
2. **Ordinamento Naturale:** Il prefisso numerico `00_` mantiene il file permanentemente in cima all'elenco dei file nella barra laterale di Obsidian.
3. **Stem Univoco Globale:** La nota puo' essere citata ovunque nel Vault con un wikilink sintetico ed inequivocabile: `[[00_Indice_Progetti]]`.
4. **Zero Collisioni:** Elimina alla radice le collisioni nel Quick Switcher e nei grafi di relazione.
