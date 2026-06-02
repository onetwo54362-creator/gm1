import os
import json
import logging
from .base import BaseExporter

logger = logging.getLogger(__name__)


class YouTubeExporter(BaseExporter):
    SERVICE_NAME = 'youtube'
    API_NAME = 'youtube'
    API_VERSION = 'v3'

    def export(self):
        print(f"  \U0001f3ac YouTube...")

        try:
            self._export_channels()
            self._export_playlists()
            self._export_liked_videos()
            self._export_subscriptions()
            self._export_uploads()
        except Exception as e:
            logger.error(f"YouTube export error: {e}")
            print(f"     \u26a0\ufe0f  YouTube error: {e}")

        self.progress.flush()
        print("     \u2705 YouTube done!")

    def _export_channels(self):
        """Export channel info."""
        if self.progress.is_done('channels'):
            return
        try:
            result = self.api_call(
                self.service.channels().list(
                    part='snippet,contentDetails,statistics', mine=True
                )
            )
            with open(
                os.path.join(self.output_dir, 'channels.json'), 'w', encoding='utf-8'
            ) as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            self.progress.mark_done('channels')
        except Exception as e:
            logger.warning(f"Failed to export channels: {e}")

    def _export_playlists(self):
        """Export all playlists and their items."""
        if self.progress.is_done('playlists'):
            return
        try:
            all_playlists = []
            result = self.api_call(
                self.service.playlists().list(
                    part='snippet,contentDetails', mine=True, maxResults=50
                )
            )
            all_playlists.extend(result.get('items', []))

            while 'nextPageToken' in result:
                page_token = result['nextPageToken']
                result = self.api_call(
                    self.service.playlists().list(
                        part='snippet,contentDetails',
                        mine=True,
                        maxResults=50,
                        pageToken=page_token,
                    )
                )
                all_playlists.extend(result.get('items', []))

            # Get items for each playlist
            for playlist in all_playlists:
                playlist['_items'] = self._get_playlist_items(playlist['id'])

            with open(
                os.path.join(self.output_dir, 'playlists.json'), 'w', encoding='utf-8'
            ) as f:
                json.dump(all_playlists, f, indent=2, ensure_ascii=False)

            self.progress.mark_done('playlists')
            print(f"     {len(all_playlists)} playlists")
        except Exception as e:
            logger.warning(f"Failed to export playlists: {e}")

    def _get_playlist_items(self, playlist_id):
        """Get all items in a playlist."""
        all_items = []
        result = self.api_call(
            self.service.playlistItems().list(
                part='snippet,contentDetails',
                playlistId=playlist_id,
                maxResults=50,
            )
        )
        all_items.extend(result.get('items', []))

        while 'nextPageToken' in result:
            page_token = result['nextPageToken']
            result = self.api_call(
                self.service.playlistItems().list(
                    part='snippet,contentDetails',
                    playlistId=playlist_id,
                    maxResults=50,
                    pageToken=page_token,
                )
            )
            all_items.extend(result.get('items', []))

        return all_items

    def _export_liked_videos(self):
        """Export liked videos."""
        if self.progress.is_done('liked_videos'):
            return
        try:
            all_liked = []
            result = self.api_call(
                self.service.videos().list(
                    part='snippet,contentDetails', myRating='like', maxResults=50
                )
            )
            all_liked.extend(result.get('items', []))

            while 'nextPageToken' in result:
                page_token = result['nextPageToken']
                result = self.api_call(
                    self.service.videos().list(
                        part='snippet,contentDetails',
                        myRating='like',
                        maxResults=50,
                        pageToken=page_token,
                    )
                )
                all_liked.extend(result.get('items', []))

            with open(
                os.path.join(self.output_dir, 'liked_videos.json'), 'w', encoding='utf-8'
            ) as f:
                json.dump(all_liked, f, indent=2, ensure_ascii=False)

            self.progress.mark_done('liked_videos')
            print(f"     {len(all_liked)} liked videos")
        except Exception as e:
            logger.warning(f"Failed to export liked videos: {e}")

    def _export_subscriptions(self):
        """Export YouTube subscriptions."""
        if self.progress.is_done('subscriptions'):
            return
        try:
            all_subs = []
            result = self.api_call(
                self.service.subscriptions().list(
                    part='snippet', mine=True, maxResults=50
                )
            )
            all_subs.extend(result.get('items', []))

            while 'nextPageToken' in result:
                page_token = result['nextPageToken']
                result = self.api_call(
                    self.service.subscriptions().list(
                        part='snippet',
                        mine=True,
                        maxResults=50,
                        pageToken=page_token,
                    )
                )
                all_subs.extend(result.get('items', []))

            with open(
                os.path.join(self.output_dir, 'subscriptions.json'),
                'w',
                encoding='utf-8',
            ) as f:
                json.dump(all_subs, f, indent=2, ensure_ascii=False)

            self.progress.mark_done('subscriptions')
            print(f"     {len(all_subs)} subscriptions")
        except Exception as e:
            logger.warning(f"Failed to export subscriptions: {e}")

    def _export_uploads(self):
        """Export your uploaded video metadata."""
        if self.progress.is_done('uploads'):
            return
        try:
            channels = self.api_call(
                self.service.channels().list(part='contentDetails', mine=True)
            )
            if not channels.get('items'):
                return

            uploads_id = channels['items'][0]['contentDetails']['relatedPlaylists'][
                'uploads'
            ]
            items = self._get_playlist_items(uploads_id)

            with open(
                os.path.join(self.output_dir, 'uploads.json'), 'w', encoding='utf-8'
            ) as f:
                json.dump(items, f, indent=2, ensure_ascii=False)

            self.progress.mark_done('uploads')
            print(f"     {len(items)} uploaded videos")
        except Exception as e:
            logger.warning(f"Failed to export uploads: {e}")
