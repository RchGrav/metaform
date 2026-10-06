"""Thin Click adapters for registered operations."""
import click
from metaform import cli

@click.command('showcase', help='Show all template features, current context and settings.')
def menu_command():
    cli.output(cli.invoke('features'))


@click.command('sample-write', help='Store text unchanged; repeat to create a retained revision.')
@click.option('--text', required=True)
@click.option('--address', default='data.showcase.note', show_default=True)
def write_command(text, address):
    cli.output(cli.invoke('write', text=text, address=address))


@click.command('sample-join', help='Attach a typed note join with its source and producing operation.')
@click.option('--text', required=True)
@click.option('--join-id', help='Revise the returned join id; omitting this creates a new join.')
def join_command(text, join_id):
    cli.output(cli.invoke('annotate', text=text, join_id=join_id))


@click.command('sample-read', help='Inspect an exact owned join and its producing occurrences.')
@click.option('--address', default='data.showcase.note', show_default=True)
@click.option('--join-id', default='note', show_default=True)
@click.option('--revision', type=int)
def read_command(address, join_id, revision):
    cli.output(cli.invoke('inspect', address=address, join_id=join_id, revision=revision))


@click.command('sample-prompt', help='Retain a supplied instruction for the deterministic authoring demo.')
@click.option('--text', required=True)
def prompt_command(text):
    cli.output(cli.invoke('prompt', text=text))


@click.command('sample-author', help='Record your answer and exact context; this demo makes no model call.')
@click.option('--answer', required=True)
@click.option('--source-revision', type=click.IntRange(min=1))
@click.option('--prompt-revision', type=click.IntRange(min=1))
def author_command(answer, source_revision, prompt_revision):
    cli.output(cli.invoke('author', answer=answer,
        source_revision=source_revision, prompt_revision=prompt_revision))


@click.command('sample-async', help='Start an asynchronous job and return its id immediately.')
@click.option('--text', required=True)
@click.option('--seconds', type=click.FloatRange(min=0), default=1.0, show_default=True)
def async_command(text, seconds):
    cli.output(cli.invoke('queue', text=text, seconds=seconds))


@click.command('sample-assignment', help='Create an activation with your prompt and print its nonce.')
@click.option('--prompt', default='Write an observation about the project. Preserve your answer as supplied.')
def assignment_command(prompt):
    cli.output(cli.invoke('assignment', prompt=prompt))


@click.command('sample-watch', help='Enable or remove the live showcase.saved event subscription.')
@click.option('--on/--off', 'enabled', default=True, show_default=True)
def watch_command(enabled):
    cli.output(cli.invoke('watch', enabled=enabled))


COMMANDS = (menu_command, write_command, join_command, read_command, prompt_command, author_command, async_command,
            assignment_command, watch_command)
