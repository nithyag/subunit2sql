# Copyright 2012 New Dream Network, LLC (DreamHost)
# Copyright 2014 Hewlett-Packard Development Company, L.P.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import os
import sys

from alembic import command as alembic_command
from alembic import config as alembic_config
from alembic import script as alembic_script
from alembic import util as alembic_util
from oslo.config import cfg
from oslo.db import options


HEAD_FILENAME = 'HEAD'


def state_path_def(*args):
    """Return an uninterpolated path relative to $state_path."""
    return os.path.join('$state_path', *args)


CONF = cfg.CONF
CONF.register_cli_opts(options.database_opts, group='database')


def do_alembic_command(config, cmd, *args, **kwargs):
    try:
        getattr(alembic_command, cmd)(config, *args, **kwargs)
    except alembic_util.CommandError as e:
        alembic_util.err(str(e))


def do_check_migration(config, cmd):
    do_alembic_command(config, 'branches')
    validate_head_file(config)


def do_upgrade_downgrade(config, cmd):
    if not CONF.command.revision and not CONF.command.delta:
        raise SystemExit('You must provide a revision or relative delta')

    revision = CONF.command.revision

    if CONF.command.delta:
        sign = '+' if CONF.command.name == 'upgrade' else '-'
        revision = sign + str(CONF.command.delta)
    else:
        revision = CONF.command.revision

    do_alembic_command(config, cmd, revision, sql=CONF.command.sql)


def do_stamp(config, cmd):
    do_alembic_command(config, cmd,
                       CONF.command.revision,
                       sql=CONF.command.sql)


def do_revision(config, cmd):
    do_alembic_command(config, cmd,
                       message=CONF.command.message,
                       autogenerate=CONF.command.autogenerate,
                       sql=CONF.command.sql)
    update_head_file(config)


def validate_head_file(config):
    script = alembic_script.ScriptDirectory.from_config(config)
    if len(script.get_heads()) > 1:
        alembic_util.err('Timeline branches unable to generate timeline')

    head_path = os.path.join(script.versions, HEAD_FILENAME)
    if (os.path.isfile(head_path) and
        open(head_path).read().strip() == script.get_current_head()):
        return
    else:
        alembic_util.err('HEAD file does not match migration timeline head')


def update_head_file(config):
    script = alembic_script.ScriptDirectory.from_config(config)
    if len(script.get_heads()) > 1:
        alembic_util.err('Timeline branches unable to generate timeline')

    head_path = os.path.join(script.versions, HEAD_FILENAME)
    with open(head_path, 'w+') as f:
        f.write(script.get_current_head())


def add_command_parsers(subparsers):
    for name in ['current', 'history', 'branches']:
        parser = subparsers.add_parser(name)
        parser.set_defaults(func=do_alembic_command)

    parser = subparsers.add_parser('check_migration')
    parser.set_defaults(func=do_check_migration)

    for name in ['upgrade', 'downgrade']:
        parser = subparsers.add_parser(name)
        parser.add_argument('--delta', type=int)
        parser.add_argument('--sql', action='store_true')
        parser.add_argument('revision', nargs='?')
        parser.add_argument('--mysql-engine',
                            default='',
                            help='Change MySQL storage engine of current '
                                 'existing tables')
        parser.set_defaults(func=do_upgrade_downgrade)

    parser = subparsers.add_parser('stamp')
    parser.add_argument('--sql', action='store_true')
    parser.add_argument('revision')
    parser.set_defaults(func=do_stamp)

    parser = subparsers.add_parser('revision')
    parser.add_argument('-m', '--message')
    parser.add_argument('--autogenerate', action='store_true')
    parser.add_argument('--sql', action='store_true')
    parser.set_defaults(func=do_revision)


command_opt = cfg.SubCommandOpt('command',
                                title='Command',
                                help='Available commands',
                                handler=add_command_parsers)

CONF.register_cli_opt(command_opt)


def main():
    config = alembic_config.Config(os.path.join(os.path.dirname(__file__),
                                                'alembic.ini'))
    config.set_main_option('script_location',
                           'subunit2sql:migrations')
    config.subunit2sql_config = CONF
    CONF()
    CONF.command.func(config, CONF.command.name)

if __name__ == "__main__":
    sys.exit(main())