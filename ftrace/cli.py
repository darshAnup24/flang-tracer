#!/usr/bin/env python3
"""
FTrace command-line interface.
Uses the new semantic correlation engine.
"""

import sys
import os
import argparse
import logging
import json
from pathlib import Path

from .engine import SemanticCorrelationEngine
from .compiler_interface import FlangNotFoundError
from .render_html import generate_html
from .render_text import render_trace_to_terminal

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def read_fortran_file(filepath: str) -> str:
    """Read Fortran source file."""
    try:
        with open(filepath, 'r') as f:
            return f.read()
    except FileNotFoundError:
        logger.error(f"File not found: {filepath}")
        sys.exit(1)
    except IOError as e:
        logger.error(f"Error reading file: {e}")
        sys.exit(1)


def trace_command(args):
    """Trace a Fortran file through all compilation stages."""
    logger.info(f"Tracing: {args.file}")

    # Read Fortran code
    code = read_fortran_file(args.file)

    # Create semantic correlation engine
    try:
        engine = SemanticCorrelationEngine()
        logger.info("Using semantic correlation engine")
    except Exception as e:
        logger.error(f"Failed to initialize engine: {e}")
        sys.exit(1)

    # Trace through all stages
    try:
        logger.info("Starting semantic correlation...")
        bundle = engine.trace_with_real_compiler(code)
        
        # Convert to dict format if needed
        if not isinstance(bundle, dict):
            bundle = bundle.to_dict()

        stats = bundle.get('metadata', {}).get('correlation_stats', {})
        logger.info(f"Correlation complete:")
        logger.info(f"  Total constructs: {len(bundle.get('nodes', []))}")
        logger.info(f"  Correlation rate: {stats.get('correlation_rate', 0):.1f}%")
        logger.info(f"  Avg FIR ops/construct: {stats.get('avg_fir_ops_per_construct', 0):.1f}")

        # Output results
        if args.format == 'html':
            output = generate_html(bundle)
            output_file = args.output or 'trace_output.html'
            with open(output_file, 'w') as f:
                f.write(output)
            logger.info(f"HTML output written to: {output_file}")

        elif args.format == 'json':
            output_file = args.output or 'trace_output.json'
            with open(output_file, 'w') as f:
                json.dump(bundle, f, indent=2)
            logger.info(f"JSON output written to: {output_file}")

        elif args.format == 'text':
            output = render_trace_to_terminal(bundle)
            if args.output:
                with open(args.output, 'w') as f:
                    f.write(output)
                logger.info(f"Text output written to: {args.output}")
            else:
                print(output)

    except FlangNotFoundError as e:
        logger.error(f"Flang compiler not found: {e}")
        logger.error("Please ensure flang-new is installed and in your PATH")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Tracing failed: {e}", exc_info=True)
        sys.exit(1)


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Flang Multi-Stage Semantic Compiler Tracer'
    )

    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # Trace command
    trace_parser = subparsers.add_parser('trace', help='Trace Fortran code through all stages')
    trace_parser.add_argument('file', help='Fortran source file')
    trace_parser.add_argument(
        '-f', '--format',
        choices=['html', 'json', 'text'],
        default='html',
        help='Output format (default: html)'
    )
    trace_parser.add_argument(
        '-o', '--output',
        help='Output file (default: trace_output.<format>)'
    )
    trace_parser.set_defaults(func=trace_command)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == '__main__':
    main()
