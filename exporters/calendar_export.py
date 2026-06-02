import os
import json
import logging
from .base import BaseExporter
from utils import safe_filename

logger = logging.getLogger(__name__)


class CalendarExporter(BaseExporter):
    SERVICE_NAME = 'calendar'
    API_NAME = 'calendar'
    API_VERSION = 'v3'

    def export(self):
        print(f"  \U0001f4c5 Google Calendar...")

        try:
            result = self.api_call(
                self.service.calendarList().list()
            )
            calendars = result.get('items', [])
        except Exception as e:
            logger.error(f"Failed to list calendars: {e}")
            print(f"     \u274c Failed: {e}")
            return

        print(f"     {len(calendars)} calendars found")

        for cal in calendars:
            cal_id = cal['id']
            cal_name = cal.get('summary', cal_id)

            if self.progress.is_done(cal_id):
                continue

            try:
                events = self._get_all_events(cal_id)

                safe_name = safe_filename(cal_name)
                output = {
                    'calendar': {
                        'id': cal_id,
                        'summary': cal_name,
                        'description': cal.get('description'),
                        'timeZone': cal.get('timeZone'),
                    },
                    'events': events,
                    'total_events': len(events),
                }

                with open(
                    os.path.join(self.output_dir, f'{safe_name}.json'),
                    'w',
                    encoding='utf-8',
                ) as f:
                    json.dump(output, f, indent=2, ensure_ascii=False)

                self.progress.mark_done(cal_id)
                print(f"     \u2705 {cal_name}: {len(events)} events")

            except Exception as e:
                logger.warning(f"Failed to export calendar '{cal_name}': {e}")
                print(f"     \u26a0\ufe0f  {cal_name}: {e}")

        self.progress.flush()
        print("     \u2705 Calendar done!")

    def _get_all_events(self, calendar_id):
        """Get all events from a calendar via pagination."""
        all_events = []
        result = self.api_call(
            self.service.events().list(
                calendarId=calendar_id,
                maxResults=2500,
                singleEvents=False,
            )
        )
        all_events.extend(result.get('items', []))

        while 'nextPageToken' in result:
            page_token = result['nextPageToken']
            result = self.api_call(
                self.service.events().list(
                    calendarId=calendar_id,
                    maxResults=2500,
                    pageToken=page_token,
                    singleEvents=False,
                )
            )
            all_events.extend(result.get('items', []))

        return all_events
