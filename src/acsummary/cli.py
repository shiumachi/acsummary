import click

@click.command()
def cli():
    """A command line interface for acsummary."""
    click.echo('Hello, world!')

if __name__ == '__main__':
    cli()