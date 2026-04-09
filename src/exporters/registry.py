"""Registry for result exporters."""

from exporters.json_exporter import export_run_result_json, export_run_metadata_json
from exporters.stix_exporter import export_run_result_stix
from exporters.zip_exporter import export_run_result_zip

EXPORTERS = {
    "json": export_run_result_json,
    "stix": export_run_result_stix,
    "zip": export_run_result_zip,
    "metadata": export_run_metadata_json
}

def get_exporter(fmt: str):
    return EXPORTERS.get(fmt)
