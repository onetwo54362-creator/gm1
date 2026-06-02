import os
import json
import base64
import logging
from tqdm import tqdm
from .base import BaseExporter

logger = logging.getLogger(__name__)


class GmailExporter(BaseExporter):
    SERVICE_NAME = 'gmail'
    API_NAME = 'gmail'
    API_VERSION = 'v1'

    def export(self, mode='full'):
        """Export Gmail data.

        Args:
            mode: 'metadata' for fast subject/from/date export,
                  'full' for complete .eml files with attachments
        """
        print(f"  \U0001f4e7 Gmail ({mode} mode)...")

        # Export labels first
        self._export_labels()

        # Get all message IDs
        message_ids = self._list_all_messages()

        # Filter already exported
        remaining = [mid for mid in message_ids if not self.progress.is_done(mid)]
        print(f"     {len(message_ids)} total emails, {len(remaining)} remaining")

        if not remaining:
            print("     \u2705 Already complete!")
            return

        if mode == 'metadata':
            self._export_metadata(remaining)
        elif mode == 'full':
            self._export_full(remaining)

        self.progress.flush()
        print(f"     \u2705 Gmail done! ({self.progress.completed_count} emails exported)")

    def _export_labels(self):
        """Export all Gmail label definitions."""
        try:
            result = self.api_call(
                self.service.users().labels().list(userId='me')
            )
            labels = result.get('labels', [])
            with open(os.path.join(self.output_dir, 'labels.json'), 'w') as f:
                json.dump(labels, f, indent=2)
            logger.info(f"Exported {len(labels)} labels")
        except Exception as e:
            logger.error(f"Failed to export labels: {e}")

    def _list_all_messages(self):
        """Get all message IDs via pagination."""
        all_ids = []
        result = self.api_call(
            self.service.users().messages().list(userId='me', maxResults=500)
        )
        all_ids.extend([m['id'] for m in result.get('messages', [])])

        page = 1
        while 'nextPageToken' in result:
            page += 1
            page_token = result['nextPageToken']
            result = self.api_call(
                self.service.users().messages().list(
                    userId='me', maxResults=500, pageToken=page_token
                )
            )
            all_ids.extend([m['id'] for m in result.get('messages', [])])
            if page % 10 == 0:
                print(f"     Scanning mailbox... {len(all_ids)} emails found")

        return all_ids

    def _export_metadata(self, message_ids):
        """Export email metadata (fast \u2014 subject, from, date, snippet) as JSON."""
        metadata_file = os.path.join(self.output_dir, 'emails_metadata.json')

        # Load existing metadata if resuming
        existing = []
        if os.path.exists(metadata_file):
            try:
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    existing = json.load(f)
            except json.JSONDecodeError:
                existing = []

        metadata = list(existing)

        for msg_id in tqdm(message_ids, desc=f'     {self.email}'):
            try:
                msg = self.api_call(
                    self.service.users().messages().get(
                        userId='me', id=msg_id, format='metadata',
                        metadataHeaders=['From', 'To', 'Subject', 'Date', 'Cc', 'Bcc']
                    )
                )
                headers = {h['name']: h['value'] for h in msg['payload']['headers']}
                metadata.append({
                    'id': msg_id,
                    'thread_id': msg.get('threadId'),
                    'from': headers.get('From'),
                    'to': headers.get('To'),
                    'cc': headers.get('Cc'),
                    'bcc': headers.get('Bcc'),
                    'subject': headers.get('Subject'),
                    'date': headers.get('Date'),
                    'snippet': msg.get('snippet'),
                    'labels': msg.get('labelIds', []),
                    'size': msg.get('sizeEstimate'),
                })
                self.progress.mark_done(msg_id)
            except Exception as e:
                logger.warning(f"Failed to fetch metadata for {msg_id}: {e}")

        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

    def _export_full(self, message_ids):
        """Export full emails as .eml files (includes attachments)."""
        eml_dir = os.path.join(self.output_dir, 'eml')
        os.makedirs(eml_dir, exist_ok=True)

        for msg_id in tqdm(message_ids, desc=f'     {self.email}'):
            try:
                msg = self.api_call(
                    self.service.users().messages().get(
                        userId='me', id=msg_id, format='raw'
                    )
                )
                raw = base64.urlsafe_b64decode(msg['raw'])
                with open(os.path.join(eml_dir, f'{msg_id}.eml'), 'wb') as f:
                    f.write(raw)
                self.progress.mark_done(msg_id)
            except Exception as e:
                logger.warning(f"Failed to export email {msg_id}: {e}")
