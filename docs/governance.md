# Manuale di Governance, Audit e Remediation (`docs/governance.md`)

Questo documento definisce gli standard di integrità del Second Brain, l'architettura diagnostica a 5 fasi e il protocollo di bonifica (remediation) governato da **VaultKeeper**.

---

## 1. La Filosofia di Governance del Vault

Un Second Brain basato su Markdown (come Obsidian) garantisce la massima longevità del dato (Future-Proofing), ma e' soggetto a entropia informativa nel corso del tempo:
- Nomi di file inconsistenti che creano collisioni di stem (`Ctrl + O`).
- Metadati YAML mancanti o con valori arbitrari (`tipo` errato).
- Tag orfani o non censiti che inquinano il grafo dei nodi.
- File multimediali e PDF orfani abbandonati nelle cartelle allegati.
- Collegamenti interni interrotti a seguito di spostamenti o rinomine manuali.

VaultKeeper trasforma la manutenzione da processo manuale e reattivo a **processo deterministico, misurabile e automatizzabile**.

---

## 2. Le 5 Fasi del Motore Diagnostico (`vk audit`)

L'audit esegue 5 livelli gerarchici di diagnostica:

### Fase 1: Storage & Filesystem
Verifica la conformità dell'albero delle cartelle rispetto ai vincoli del file system e del sistema operativo:
- **Lunghezza Percorsi (Max Path Length):** Previene errori di backup o sincronizzazione rilevando percorsi superiori a `config.max_path_length` (default: 240 caratteri).
- **Estensioni Consentite:** Rileva file con estensioni non autorizzate (es. file binari o eseguibili non ammessi nel Vault).
- **File Pesanti (Heavy Files):** Isola file con dimensione superiore a `config.heavy_file_threshold_mb` (default: 50 MB), raccomandandone il trasferimento in Cold Storage (Archive).
- **File Nascosti:** Rileva residui temporanei o file orfani del sistema operativo (`.DS_Store`, `Thumbs.db`).

### Fase 2: Convenzioni di Naming
Verifica che note e cartelle rispettino la strategia di denominazione configurata (`naming_style = "Title_Case"`):
- **Title_Case con Underscore:** Parole con iniziale maiuscola separate da underscore (es. `Architettura_Di_Sistema.md`).
- **Conservazione Prefissi Johnny.Decimal:** Rispetta schemi numerici (es. `00_`, `10-19_`, `01_`).
- **Conservazione Acronimi:** Preserva maiuscoli integrali per acronimi censiti (`AI`, `API`, `AWS`, `BCG`, `CRM`, `HPC`, `IT`, `JEMORE`, `MECE`, `SQL`, `UX`, `MOC`, `PKM`).
- **Caratteri Proibiti:** Segnala la presenza di caratteri non ammessi o rischiosi nei nomi file (`' " : ? * ! & | < > , \ ( )`).

### Fase 3: Frontmatter YAML e Tipizzazione
Valuta l'integrità semantica delle intestazioni frontmatter:
- **Presenza del Frontmatter:** Ogni nota deve iniziare con delimitatori validi `---`.
- **Campi Obbligatori:** Verifica la presenza dei campi cardine (`tipo` e `tags`).
- **Validita' del Campo `tipo`:** Il valore deve appartenere rigorosamente al vocabolario controllato:
  - `Appunto` (note di studio, sintesi concettuali, elaborazioni)
  - `Contatto` (schede anagrafiche e CRM personale)
  - `Progetto` (iniziative con obiettivi e scadenze)
  - `Risorsa` (materiali di riferimento, cheat-sheet, estratti esterni)
  - `Indice` (MOC e note di orientamento di cartella)
  - `Sistema` (file di configurazione, tassonomie, template)

### Fase 4: Tassonomia Controllata dei Tag
Previene l'esplosione incontrollata di tag casuali:
- **Verifica rispetto a `00_Tassonomia_Tag.md`:** Se `strict_taxonomy = true`, qualsiasi tag (nel frontmatter o inline) non censito nella tassonomia ufficiale genera una violazione bloccante.
- **Protezione Falsi Positivi:**
  - *Direttive C/C++:* Ignora `#include`, `#define`, `#pragma`, `#ifdef` presenti nel testo.
  - *Codici Colore Esadecimali:* Ignora codici colore come `#FFFFFF`, `#000000`, `#2a3b4c`.
  - *Blocchi di Codice e Formule:* Non estrae mai tag all'interno di blocchi `` `...` ``, ```` ```...``` ```` o LaTeX `$...$`.

### Fase 5: Integrita' dei Collegamenti e Allegati
Preserva il grafo di conoscenza del Second Brain:
- **Wikilink Rotti:** Rileva collegamenti `[[Destinazione]]` verso note o sezioni inesistenti.
- **Embed Multimediali Rotti:** Rileva `![[Immagine.png]]` verso file non presenti sul disco.
- **Collisioni di Stem:** Rileva note omonime collocate in cartelle differenti che creano ambiguita' nel Quick Switcher di Obsidian.
- **Allegati Orfani:** Isola file collocati nelle cartelle allegati non referenziati da alcuna nota del Vault.

---

## 3. Calcolo del Vault Health Score

Il punteggio di salute parte da **100.0 / 100.0** e subisce detrazioni ponderate in base alla gravita' del problema:

$$\text{Health Score} = 100.0 - \sum \text{Penalita'}$$

| Categoria di Violazione | Fase | Penalita' per Singola Occorrenza |
| :--- | :---: | :---: |
| Collegamento rotto o embed multimediale mancante | 5 | **-3.0** |
| Percorso che supera la lunghezza massima consentita | 1 | **-2.0** |
| Nota Markdown priva di intestazione YAML frontmatter | 3 | **-2.0** |
| Valore `tipo` mancante o non appartenente al vocabolario consentito | 3 | **-1.5** |
| File con estensione non ammessa nel Vault | 1 | **-1.0** |
| File multimediale orfano non citato da alcuna nota | 5 | **-1.0** |
| Violazione convenzione di naming (file o cartella) | 2 | **-0.5** |
| Tag utilizzato ma non censito nella tassonomia ufficiale | 4 | **-0.5** |

Il punteggio e' vincolato nell'intervallo tra `0.0` e `100.0`. Un Vault eccellente registra un punteggio $\ge 95.0$.

---

## 4. Protocollo Sistemico di Bonifica (Remediation)

Quando l'audit rileva anomalie (`Exit Code = 2`), la procedura di bonifica segue questo ordine deterministico:

```text
1. Normalizzazione Nomi
   └─► vk normalize-names --dry-run
   └─► vk normalize-names

2. Rettifica Metadati Frontmatter
   └─► vk frontmatter set-type --target <nota> --type <tipo>
   └─► vk frontmatter sanitize-tags

3. Rimozione / Archiviazione Allegati Orfani
   └─► vk clean-attachments --dry-run
   └─► vk clean-attachments

4. Rigenerazione Mappa di Contenuti (MOC)
   └─► vk generate-indices --all

5. Riesecuzione Audit di Certificazione
   └─► vk audit
```
