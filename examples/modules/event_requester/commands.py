"""Click adapters for the requester operations."""
import click
from metaform import cli


@click.command('request-work', help='Send a stored prompt to the harness module and return its queued job.')
@click.option('--prompt', required=True, help='Exact instructions for the configured agent harness.')
def request_command(prompt):
    cli.output(cli.invoke('request', prompt=prompt))


COMMANDS = (request_command,)
