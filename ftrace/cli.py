import click
import json
import os
import sys

# Hack to adjust path if `ftrace` is executed inside its own directory.
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ftrace.engine import CorrelationEngine
from ftrace.render_text import render_trace_to_terminal
from ftrace.render_html import generate_html
from ftrace.render_json import export_json
from tests.mocks import get_c01_mock_bundle

@click.group()
def cli():
    """Flang Multi-Stage Compilation Pipeline Tracer"""
    pass

@cli.command()
@click.argument('source_file', type=click.Path(exists=True))
def trace(source_file):
    """Trace a Fortran source file through the pipeline."""
    click.echo(f"Tracing {source_file}...")
    
    # Mock behavior since real flang is currently not compiled!
    click.echo("LLVM build not detected natively, substituting with Engine Mock (C01)...")
    
    bundle = get_c01_mock_bundle()
    render_trace_to_terminal(bundle)

@cli.command()
@click.option('--stage', type=click.Choice(['parse', 'sema', 'hlfir', 'fir', 'llvm']), required=True)
def show(stage):
    """Show the output of a specific compilation stage."""
    click.echo(f"Showing stage definition: {stage} for active cache bundle.")

@cli.command()
@click.argument('old_file', type=click.Path(exists=True))
@click.argument('new_file', type=click.Path(exists=True))
@click.option('--construct', required=True, help='Construct ID to difference (e.g., C05)')
def diff(old_file, new_file, construct):
    """Compare lowering of a specific construct between two file versions."""
    click.echo(f"Diffing {construct} between {old_file} and {new_file}")

@cli.command()
@click.option('--format', type=click.Choice(['html', 'json', 'text']), default='text')
def export(format):
    """Export the currently correlated trace bundle to the specified format."""
    click.echo(f"Exporting mock bundle in {format} format...")
    bundle = get_c01_mock_bundle()
    
    if format == 'html':
        html_output = generate_html(bundle)
        with open("output.html", "w") as f:
            f.write(html_output)
        click.echo("Written to output.html")
    elif format == 'json':
        with open("output.json", "w") as f:
            export_json(bundle, f)
        click.echo("Written to output.json")
    else:
        render_trace_to_terminal(bundle)

if __name__ == '__main__':
    cli()
