import json

def export_json(trace_bundle, fp):
    """Exports trace bundle into standard JSON schema format natively consumed by LSPs."""
    json.dump(trace_bundle, fp, indent=2)
