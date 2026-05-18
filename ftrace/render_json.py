import json
import logging

logger = logging.getLogger(__name__)


def export_json(trace_bundle, fp):
    """
    Export trace bundle in consistent schema.
    """

    if not trace_bundle or not isinstance(trace_bundle, dict):
        logger.error("Invalid trace bundle format")

        output = {
            "nodes": [],
            "metadata": {
                "error": "Invalid trace bundle format",
                "schema_version": "1.0"
            }
        }

    else:
        nodes = trace_bundle.get('nodes', [])
        if not isinstance(nodes, list):
            nodes = []

        output = {
            "nodes": nodes,
            "metadata": {
                "total_nodes": len(nodes),
                "schema_version": "1.0"
            }
        }

    try:
        json.dump(output, fp, indent=2, ensure_ascii=True)
        logger.info("JSON export successful")

    except Exception as e:
        logger.error(f"Error during JSON export: {e}")
        raise