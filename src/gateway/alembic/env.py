from logging.config import fileConfig

from alembic import context
from alembic.operations import ops
from sqlalchemy import engine_from_config, pool

from gateway import models

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# add your model's MetaData object here
# for 'autogenerate' support
target_metadata = models.Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline():
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        render_as_batch=True,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    def _no_sqlite_sequence(op):
        return not ((isinstance(op, ops.DropTableOp) or isinstance(op, ops.CreateTableOp)) and op.table_name == 'sqlite_sequence')

    def process_revision_directives(context, revision, directives):
        script = directives[0]
        if config.cmd_opts.autogenerate:  # type: ignore
            for directive in (script.upgrade_ops, script.downgrade_ops):
                directive.ops = [x for x in directive.ops if _no_sqlite_sequence(x)]

            if script.upgrade_ops.is_empty():
                directives[:] = []

    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            process_revision_directives=process_revision_directives,
            render_as_batch=True,
            dialect_opts={"paramstyle": "named"}
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    # Interpret the config file for Python logging.
    # This line sets up loggers basically.
    fileConfig(config.config_file_name)  # type: ignore

    run_migrations_offline()
else:
    run_migrations_online()
