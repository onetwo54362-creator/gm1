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


def cmd_auto(args):
    """Seamless automated loop for Termux users."""
    pending_file = 'accounts_pending.txt'
    completed_file = 'accounts_completed.txt'
    
    # Migrate old accounts.txt if it exists
    if os.path.exists('accounts.txt') and not os.path.exists(pending_file):
        os.rename('accounts.txt', pending_file)

    accounts = load_accounts_file(pending_file)
    
    print("\n\U0001f916 Google Data Exporter - Auto Mode")
    print("=" * 45)
    
    # 1. Prompt for new accounts
    response = input(f"Do you want to add more accounts to the queue? (y/N): ").strip().lower()
    if response == 'y':
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
        
        # Save back to pending
        with open(pending_file, 'w') as f:
            for email in accounts:
                f.write(f'{email}\n')
        print(f'\n\u2705 Queue updated. Total pending accounts: {len(accounts)}\n')
        
    if not accounts:
        print("\u274c No accounts in the queue. Exiting.")
        return

    # 2. Process each account
    services = ALL_SERVICES if args.services == 'all' else set(s.strip() for s in args.services.split(','))
    
    for email in list(accounts): # Use list() to copy so we can modify the original
        print(f"\n{'=' * 50}")
        print(f'\U0001f4ec Processing: {email}')
        print('=' * 50)
        
        # A. Setup
        try:
            if not setup_account(email):
                print(f"   \u274c Setup failed or was aborted for {email}. Skipping export.")
                continue
        except Exception as e:
            print(f'   \u274c Failed to setup {email}: {e}')
            continue
            
        # B. Export
        creds = load_credentials(email)
        if not creds:
            print('   \u26a0\ufe0f  Could not load credentials. Skipping export.')
            continue
            
        export_success = True
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
                print(f'   \u274c {service_name} export failed: {e}')
                logging.getLogger().error(f'{service_name} export failed for {email}', exc_info=True)
                export_success = False
                
        # C. Mark Completed
        if export_success:
            accounts.remove(email)
            # Update pending file
            with open(pending_file, 'w') as f:
                for a in accounts:
                    f.write(f'{a}\n')
            # Append to completed file
            with open(completed_file, 'a') as f:
                f.write(f'{email}\n')
            print(f"\n\u2728 Finished and marked {email} as completed!")
        else:
            print(f"\n\u26a0\ufe0f Finished with errors for {email}. It remains in the pending queue.")

    print(f"\n{'=' * 50}")
    print("\u2705 All done! You can run python main.py again anytime to continue.")

def cmd_setup(args):
    """Legacy setup command — redirects to auto mode."""
    cmd_auto(args)


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

    # Auto command (Default)
    auto_parser = subparsers.add_parser('auto', help='Run interactive setup and export loop (Default)')
    auto_parser.add_argument('--output', '-o', default='exports', help='Output directory')
    auto_parser.add_argument('--gmail-mode', choices=['full', 'metadata'], default='full')
    auto_parser.add_argument('--services', default='all')

    # Setup command
    subparsers.add_parser('setup', help='Authenticate Google accounts')

    # Export command
    export_parser = subparsers.add_parser('export', help='Export data from all accounts')
    export_parser.add_argument('--output', '-o', default='exports', help='Output directory')
    export_parser.add_argument('--gmail-mode', choices=['full', 'metadata'], default='full')
    export_parser.add_argument('--services', default='all')

    # Status command
    status_parser = subparsers.add_parser('status', help='Show export progress')
    status_parser.add_argument('--output', '-o', default='exports', help='Export directory to check')

    # Set auto as default if no command provided
    args = parser.parse_args()
    if not args.command:
        args.command = 'auto'

    setup_logging(getattr(args, 'verbose', False))

    commands = {
        'auto': cmd_auto,
        'setup': cmd_setup,
        'export': cmd_export,
        'status': cmd_status,
    }
    commands[args.command](args)


if __name__ == '__main__':
    main()
