import os
import io
import json
import logging
from tqdm import tqdm
from googleapiclient.http import MediaIoBaseDownload
from .base import BaseExporter
from utils import safe_filename

logger = logging.getLogger(__name__)

# Google Workspace MIME types -> export formats
EXPORT_FORMATS = {
    'application/vnd.google-apps.document': (
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        '.docx',
    ),
    'application/vnd.google-apps.spreadsheet': (
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        '.xlsx',
    ),
    'application/vnd.google-apps.presentation': (
        'application/vnd.openxmlformats-officedocument.presentationml.presentation',
        '.pptx',
    ),
    'application/vnd.google-apps.drawing': (
        'application/pdf',
        '.pdf',
    ),
}

# These Google-only types cannot be exported as files
SKIP_MIMES = {
    'application/vnd.google-apps.form',
    'application/vnd.google-apps.map',
    'application/vnd.google-apps.site',
    'application/vnd.google-apps.shortcut',
    'application/vnd.google-apps.folder',
}


class DriveExporter(BaseExporter):
    SERVICE_NAME = 'drive'
    API_NAME = 'drive'
    API_VERSION = 'v3'

    def export(self):
        print(f"  \U0001f4c1 Google Drive...")

        # List all files
        files = self._list_all_files()
        remaining = [f for f in files if not self.progress.is_done(f['id'])]
        print(f"     {len(files)} total files, {len(remaining)} to download")

        if not remaining:
            print("     \u2705 Already complete!")
            return

        # Save file listing for reference
        with open(
            os.path.join(self.output_dir, 'file_listing.json'), 'w', encoding='utf-8'
        ) as f:
            json.dump(files, f, indent=2, ensure_ascii=False)

        # Download each file
        for file_info in tqdm(remaining, desc=f'     {self.email}'):
            self._download_file(file_info)

        self.progress.flush()
        print(f"     \u2705 Drive done! ({self.progress.completed_count} files)")

    def _list_all_files(self):
        """List all files in Drive."""
        all_files = []
        result = self.api_call(
            self.service.files().list(
                fields='nextPageToken, files(id, name, mimeType, size, modifiedTime, parents)',
                pageSize=1000,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
            )
        )
        all_files.extend(result.get('files', []))

        while 'nextPageToken' in result:
            page_token = result['nextPageToken']
            result = self.api_call(
                self.service.files().list(
                    fields='nextPageToken, files(id, name, mimeType, size, modifiedTime, parents)',
                    pageSize=1000,
                    pageToken=page_token,
                    supportsAllDrives=True,
                    includeItemsFromAllDrives=True,
                )
            )
            all_files.extend(result.get('files', []))

        return all_files

    def _download_file(self, file_info):
        """Download a single file from Drive."""
        file_id = file_info['id']
        name = safe_filename(file_info['name'])
        mime = file_info['mimeType']

        if mime in SKIP_MIMES:
            self.progress.mark_done(file_id)
            return

        try:
            if mime in EXPORT_FORMATS:
                export_mime, ext = EXPORT_FORMATS[mime]
                request = self.service.files().export_media(
                    fileId=file_id, mimeType=export_mime
                )
                path = os.path.join(self.output_dir, f'{name}{ext}')
            else:
                request = self.service.files().get_media(fileId=file_id)
                path = os.path.join(self.output_dir, name)

            # Handle duplicate filenames by appending part of the ID
            if os.path.exists(path):
                base, ext_part = os.path.splitext(path)
                path = f'{base}_{file_id[:8]}{ext_part}'

            buf = io.BytesIO()
            downloader = MediaIoBaseDownload(buf, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()

            with open(path, 'wb') as f:
                f.write(buf.getvalue())

            self.progress.mark_done(file_id)

        except Exception as e:
            logger.warning(f"Failed to download '{file_info['name']}': {e}")
