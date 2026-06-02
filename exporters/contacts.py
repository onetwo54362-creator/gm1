import os
import json
import logging
from .base import BaseExporter

logger = logging.getLogger(__name__)


class ContactsExporter(BaseExporter):
    SERVICE_NAME = 'contacts'
    API_NAME = 'people'
    API_VERSION = 'v1'

    def export(self):
        print(f"  \U0001f464 Google Contacts...")

        if self.progress.is_done('contacts'):
            print("     \u2705 Already complete!")
            return

        try:
            all_contacts = self._list_all_contacts()

            with open(
                os.path.join(self.output_dir, 'contacts.json'), 'w', encoding='utf-8'
            ) as f:
                json.dump(all_contacts, f, indent=2, ensure_ascii=False)

            self.progress.mark_done('contacts')
            print(f"     \u2705 Contacts done! ({len(all_contacts)} contacts)")
        except Exception as e:
            logger.error(f"Contacts export failed: {e}")
            print(f"     \u274c Failed: {e}")

    def _list_all_contacts(self):
        """List all contacts via the People API."""
        all_contacts = []
        page_token = None

        while True:
            kwargs = {
                'resourceName': 'people/me',
                'pageSize': 1000,
                'personFields': (
                    'names,emailAddresses,phoneNumbers,addresses,'
                    'organizations,birthdays,biographies,urls,photos'
                ),
            }
            if page_token:
                kwargs['pageToken'] = page_token

            result = self.api_call(
                self.service.people().connections().list(**kwargs)
            )

            connections = result.get('connections', [])
            all_contacts.extend(connections)

            page_token = result.get('nextPageToken')
            if not page_token:
                break

        return all_contacts
