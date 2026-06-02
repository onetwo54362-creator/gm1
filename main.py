#!/usr/bin/env python3
"""
Google Account Data Exporter

Export Gmail, Drive, Calendar, YouTube, and Contacts data
from multiple Google accounts. Designed for Termux on Android.

Usage:
    python main.py setup                          # Authenticate accounts
    python main.py export                         # Export everything
    python main.py export --gmail-mode metadata   # Fast metadata-only
    python main.py export --services gmail,drive   # Specific services
    python main.py status                         # Check progress
"""

import argparse
import logging
import os
import json
from pathlib import Path

from auth import (
    setup_account,
    load_credentials,
    list_saved_accounts,
    load_accounts_file,
)
from exporters import (
    GmailExporter,
    DriveExporter,
    CalendarExporter,
    YouTubeExporter,
    ContactsExporter,
)

ALL_SERVICES = {'gmail', 'drive', 'calendar', 'youtube', 'contacts'}

EXPORTER_MAP = {
    'gmail': GmailExporter,
    'drive': DriveExporter,
    'calendar': CalendarExporter,
    'youtube': YouTubeExporter,
    'contacts': ContactsExporter,
}


def setup_logging(verbose=False):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%H:%M:%S',
    )
    # Suppress noisy library logs
    logging.getLogger('googleapiclient.discovery_cache').setLevel(logging.ERROR)
    logging.getLogger('google.auth.transport.requests').setLevel(logging.WARNING)


def cmd_setup(args):
    """Authenticate accounts listed in accounts.txt or input by user."""
    accounts = load_accounts_file('accounts.txt')

    if not accounts:
        print('No accounts found in accounts.txt.')
        print('\nPlease paste the Gmail addresses you want to export (one per line).')
        print('When you are done, leave a blank line and press Enter:')
        
        while True:
            try:
                line = input().strip()
                if not line:
                    break
                if line and not line.startswith('#'):
                    accounts.append(line)
            except EOFError:
                break
                
        if not accounts:
            print('\u274c No accounts entered. Exiting.')
            return
            
        with open('accounts.txt', 'w') as f:
            for email in accounts:
                f.write(f'{email}\n')
        print(f'\n\u2705 Saved {len(accounts)} account(s) to accounts.txt\n')

    print(f'Found {len(accounts)} account(s) to setup.\n')

    success = 0
    for email in accounts:
        try:
            if setup_account(email):
                success += 1
        except Exception as e:
            print(f'\u274c Failed to setup {email}: {e}')

    print(f"\n{'=' * 40}")
    print(f'\u2705 {success}/{len(accounts)} accounts authenticated')
    if success > 0:
        print("   Run 'python main.py export' to start exporting")


def cmd_export(args):
    """Export data from all authenticated accounts."""
    accounts = list_saved_accounts()

    if not accounts:
        print('\u274c No authenticated accounts found.')
        print("   Run 'python main.py setup' first.")
        return

    # Determine which services to export
    if args.services == 'all':
        services = ALL_SERVICES
    else:
        services = set(s.strip() for s in args.services.split(','))
        invalid = services - ALL_SERVICES
        if invalid:
            print(f'\u274c Unknown services: {invalid}')
            print(f'   Valid options: {ALL_SERVICES}')
            return

    print(f'Exporting {len(accounts)} account(s)...')
    print(f'Export directory: {os.path.abspath(args.output)}')
    print(f'Gmail mode: {args.gmail_mode}')
    print(f'Services: {", ".join(sorted(services))}')

    for email in accounts:
        print(f"\n{'=' * 50}")
        print(f'\U0001f4ec {email}')
        print('=' * 50)

        creds = load_credentials(email)
        if not creds:
            print('   \u26a0\ufe0f  Skipping \u2014 could not load credentials')
            continue

        for service_name in ['gmail', 'drive', 'calendar', 'youtube', 'contacts']:
            if service_name not in services:
                continue

            try:
                exporter_cls = EXPORTER_MAP[service_name]
                exporter = exporter_cls(creds, email, args.output)

                if service_name == 'gmail':
                    exporter.export(mode=args.gmail_mode)
                else:
                    exporter.export()
            except Exception as e:
                print(f'   \u274c {service_name} failed: {e}')
                logging.getLogger().error(
                    f'{service_name} export failed for {email}', exc_info=True
                )

    print(f"\n{'=' * 50}")
    print(f'\u2705 Export complete! Files saved to: {os.path.abspath(args.output)}/')


def cmd_status(args):
    """Show export progress for all accounts."""
    accounts = list_saved_accounts()

    if not accounts:
        print('No authenticated accounts.')
        print("Run 'python main.py setup' first.")
        return

    print(f'Authenticated accounts: {len(accounts)}\n')

    for email in accounts:
        print(f'\U0001f4ec {email}')

        progress_dir = Path(args.output) / email / '.progress'
        if not progress_dir.exists():
            print('   No exports yet\n')
            continue

        for pfile in sorted(progress_dir.glob('*.json')):
            try:
                with open(pfile) as f:
                    data = json.load(f)
                service = pfile.stem
                count = data.get('total_completed', 0)
                updated = data.get('last_updated', 'unknown')
                print(f'   {service}: {count} items exported (last: {updated})')
            except (json.JSONDecodeError, KeyError):
                pass
        print()


def main():
    parser = argparse.ArgumentParser(
        description=(
            'Export Google account data '
            '(Gmail, Drive, Calendar, YouTube, Contacts)'
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py setup                          # Authenticate accounts
  python main.py export                         # Export everything
  python main.py export --gmail-mode metadata   # Fast: metadata only
  python main.py export --services gmail,drive   # Specific services only
  python main.py status                         # Check progress
        """,
    )
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose logging')

    subparsers = parser.add_subparsers(dest='command', help='Command to run')

    # Setup command
    subparsers.add_parser('setup', help='Authenticate Google accounts')

    # Export command
    export_parser = subparsers.add_parser('export', help='Export data from all accounts')
    export_parser.add_argument(
        '--output',
        '-o',
        default='exports',
        help='Output directory (default: exports/)',
    )
    export_parser.add_argument(
        '--gmail-mode',
        choices=['full', 'metadata'],
        default='full',
        help='Gmail export mode: full (.eml) or metadata (JSON, much faster)',
    )
    export_parser.add_argument(
        '--services',
        default='all',
        help=(
            'Comma-separated services to export (default: all). '
            'Options: gmail,drive,calendar,youtube,contacts'
        ),
    )

    # Status command
    status_parser = subparsers.add_parser('status', help='Show export progress')
    status_parser.add_argument(
        '--output',
        '-o',
        default='exports',
        help='Export directory to check (default: exports/)',
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    setup_logging(getattr(args, 'verbose', False))

    commands = {
        'setup': cmd_setup,
        'export': cmd_export,
        'status': cmd_status,
    }
    commands[args.command](args)


if __name__ == '__main__':
    main()
