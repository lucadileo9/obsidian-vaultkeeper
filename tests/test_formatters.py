"""Unit tests for OutputFormatter serialization engine."""

import json

import yaml

from vaultkeeper.utils.formatters import OutputFormat, format_output, render_markdown_table


def test_render_markdown_table() -> None:
    """Verify markdown table formatting with column alignment and pipes."""
    headers = ["Nome", "Stato", "Note"]
    rows = [
        ["Progetto Alpha", "Attivo", "Priorita' alta"],
        ["Nota Beta", "Archiviato", "Dettagli | con pipe"],
    ]
    table = render_markdown_table(headers, rows)
    lines = table.splitlines()

    assert len(lines) == 4
    assert lines[0] == "| Nome | Stato | Note |"
    assert lines[1] == "| :--- | :--- | :--- |"
    assert lines[2] == "| Progetto Alpha | Attivo | Priorita' alta |"
    assert "Dettagli \\| con pipe" in lines[3]


def test_format_output_json() -> None:
    """Verify JSON output serialization."""
    data = [{"title": "Alpha", "count": 42}, {"title": "Beta", "count": 7}]
    res = format_output(data, format=OutputFormat.JSON)
    parsed = json.loads(res)
    assert len(parsed) == 2
    assert parsed[0]["title"] == "Alpha"
    assert parsed[1]["count"] == 7


def test_format_output_yaml() -> None:
    """Verify YAML output serialization."""
    data = {"tipo": "Progetto", "tags": ["area/studio", "stato/attivo"]}
    res = format_output(data, format=OutputFormat.YAML)
    parsed = yaml.safe_load(res)
    assert parsed["tipo"] == "Progetto"
    assert "area/studio" in parsed["tags"]


def test_format_output_csv() -> None:
    """Verify CSV output serialization for list of dicts."""
    data = [{"colA": "val1", "colB": "val2"}, {"colA": "val3", "colB": "val4"}]
    res = format_output(data, format=OutputFormat.CSV)
    lines = res.splitlines()
    assert lines[0] == "colA,colB"
    assert lines[1] == "val1,val2"
    assert lines[2] == "val3,val4"


def test_format_output_markdown_list_and_dict() -> None:
    """Verify Markdown table generation for dict and list of dicts."""
    # List of dicts
    data_list = [{"Nome": "Alpha", "Tipo": "Progetto"}]
    res_list = format_output(data_list, format=OutputFormat.MD, title="Miei Progetti")
    assert "## Miei Progetti" in res_list
    assert "| Nome | Tipo |" in res_list
    assert "| Alpha | Progetto |" in res_list

    # Single dict
    data_dict = {"status": "ok", "items": 5}
    res_dict = format_output(data_dict, format=OutputFormat.MD)
    assert "| Proprieta | Valore |" in res_dict
    assert "| status | ok |" in res_dict


def test_format_output_empty_list() -> None:
    """Verify clean output for empty list."""
    res = format_output([], format=OutputFormat.MD)
    assert "(Nessun elemento trovato)" in res


def test_output_format_from_str() -> None:
    """Verify robust case-insensitive string parsing."""
    assert OutputFormat.from_str("MD") == OutputFormat.MD
    assert OutputFormat.from_str("json") == OutputFormat.JSON
    assert OutputFormat.from_str("Yaml") == OutputFormat.YAML
    assert OutputFormat.from_str("CSV") == OutputFormat.CSV
    assert OutputFormat.from_str("unknown") == OutputFormat.MD


def test_format_output_edge_cases() -> None:
    """Verify CSV scalar, list of primitives, and markdown scalar formatting."""
    # CSV scalar
    csv_scalar = format_output("simple_string", format=OutputFormat.CSV)
    assert "value" in csv_scalar
    assert "simple_string" in csv_scalar

    # CSV list of strings
    csv_list = format_output(["itemA", "itemB"], format=OutputFormat.CSV)
    assert "item" in csv_list
    assert "itemA" in csv_list

    # Markdown scalar
    md_scalar = format_output(12345, format=OutputFormat.MD)
    assert md_scalar == "12345"

    # Custom object with to_dict
    class CustomObj:
        def to_dict(self):
            return {"key": "val"}

    obj_res = format_output(CustomObj(), format=OutputFormat.JSON)
    assert '"key": "val"' in obj_res
