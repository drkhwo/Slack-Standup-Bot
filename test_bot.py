"""
Tests for Slack Standup Bot
Run: python -m pytest test_bot.py -v
or: python test_bot.py
"""

import os
import json
import re
import sys
import unittest
from unittest.mock import MagicMock, patch, call
from datetime import date
from pathlib import Path

# Mock external dependencies before importing main
sys.modules['slack_bolt'] = MagicMock()
sys.modules['slack_bolt.adapter'] = MagicMock()
sys.modules['slack_bolt.adapter.socket_mode'] = MagicMock()
sys.modules['supabase'] = MagicMock()
sys.modules['apscheduler'] = MagicMock()
sys.modules['apscheduler.schedulers'] = MagicMock()
sys.modules['apscheduler.schedulers.background'] = MagicMock()
sys.modules['dotenv'] = MagicMock()

# Mock load_dotenv so it doesn't read .env
with patch.dict('os.environ', {
    'SLACK_BOT_TOKEN': 'xoxb-test-token',
    'SLACK_APP_TOKEN': 'xapp-test-token',
    'SUPABASE_URL': 'https://test.supabase.co',
    'SUPABASE_KEY': 'test-key',
    'CHANNEL_ID': 'C08UT7VP2TA',
}):
    import importlib
    import main as bot_module


# ---------------------------------------------------------
# TC-01: Configuration and environment variables
# ---------------------------------------------------------
class TestConfiguration(unittest.TestCase):

    def test_channel_id_is_set(self):
        """TC-01-01: CHANNEL_ID must be set"""
        self.assertIsNotNone(bot_module.CHANNEL_ID)
        self.assertNotEqual(bot_module.CHANNEL_ID, "")

    def test_slack_bot_token_is_set(self):
        """TC-01-02: SLACK_BOT_TOKEN must be set"""
        self.assertIsNotNone(bot_module.SLACK_BOT_TOKEN)

    def test_supabase_url_is_set(self):
        """TC-01-03: SUPABASE_URL must be set"""
        self.assertIsNotNone(bot_module.SUPABASE_URL)

    def test_team_user_ids_not_empty(self):
        """TC-01-04: TEAM_USER_IDS must contain at least one user"""
        self.assertIsInstance(bot_module.TEAM_USER_IDS, list)
        self.assertGreater(len(bot_module.TEAM_USER_IDS), 0)

    def test_gtm_users_are_in_team_roster(self):
        """TC-01-05: GTM members are included in standup report tracking"""
        self.assertIn("U0BMCE4HM7D", bot_module.TEAM_USER_IDS)  # Arman
        self.assertIn("U0BQ926P1B4", bot_module.TEAM_USER_IDS)  # Vadym Netrebko
        self.assertNotIn("U0B8JM8QSBZ", bot_module.TEAM_USER_IDS)  # ruru

    def test_gena_is_in_team_roster(self):
        """TC-01-06: Gena is included in standup report tracking"""
        self.assertIn("U09RAPHVDPG", bot_module.TEAM_USER_IDS)
        self.assertEqual(bot_module.TEAM_MAPPING["U09RAPHVDPG"]["email"], "henadz@replika.com")

    def test_deactivated_users_are_excluded_from_team_roster(self):
        """TC-01-07: Deactivated Slack users are excluded from active reporting"""
        deactivated_user_ids = {
            "U097GKF641M",  # Cristian
            "U08MW9K5K0U",  # Ban
            "U097GKK3UUX",  # Georgi Todorov
            "U09T69U1Y5V",  # Sebastian
            "U088WHYP2P6",  # Gvantsa
            "U0B8285T563",  # matei
        }
        self.assertTrue(deactivated_user_ids.issubset(bot_module.DEACTIVATED_USER_IDS))
        self.assertTrue(deactivated_user_ids.isdisjoint(bot_module.TEAM_MAPPING))
        self.assertTrue(deactivated_user_ids.isdisjoint(bot_module.TEAM_USER_IDS))

    def test_deactivated_ids_override_stale_mapping_entries(self):
        """TC-01-08: A stale mapping entry cannot reactivate a deactivated user"""
        original_mapping = bot_module.TEAM_MAPPING
        stale_entries = {
            "U097GKF641M": {
                "vt_user_id": "slack-cristian-id",
                "name": "Cristian Matzov",
                "email": "cristian@example.com",
            },
            "U08MW9K5K0U": {
                "vt_user_id": "slack-ban-id",
                "name": "Ban Markovic",
                "email": "ban@example.com",
            },
            "U097GKK3UUX": {
                "vt_user_id": "slack-georgi-id",
                "name": "Georgi Todorov",
                "email": "georgi@example.com",
            },
        }
        bot_module.TEAM_MAPPING = {**original_mapping, **stale_entries}
        try:
            roster = bot_module._build_team_user_ids()
        finally:
            bot_module.TEAM_MAPPING = original_mapping

        self.assertTrue(set(stale_entries).isdisjoint(roster))

    def test_daily_thread_ts_initially_none(self):
        """TC-01-06: daily_thread_ts is initially None"""
        self.assertTrue(hasattr(bot_module, 'daily_thread_ts'))


# ---------------------------------------------------------
# TC-02: Supabase connection
# ---------------------------------------------------------
class TestSupabaseClient(unittest.TestCase):

    def test_get_supabase_client_returns_none_without_credentials(self):
        """TC-02-01: get_supabase_client() returns None without credentials"""
        with patch.dict('os.environ', {}, clear=True):
            original_url = bot_module.SUPABASE_URL
            original_key = bot_module.SUPABASE_KEY
            bot_module.SUPABASE_URL = None
            bot_module.SUPABASE_KEY = None
            result = bot_module.get_supabase_client()
            bot_module.SUPABASE_URL = original_url
            bot_module.SUPABASE_KEY = original_key
            self.assertIsNone(result)

    def test_get_supabase_client_calls_create_client(self):
        """TC-02-02: get_supabase_client() calls create_client with correct params"""
        mock_client = MagicMock()
        with patch('main.create_client', return_value=mock_client) as mock_create:
            bot_module.SUPABASE_URL = 'https://test.supabase.co'
            bot_module.SUPABASE_KEY = 'test-key'
            result = bot_module.get_supabase_client()
            mock_create.assert_called_once_with('https://test.supabase.co', 'test-key')
            self.assertEqual(result, mock_client)


# ---------------------------------------------------------
# TC-03: post_daily_thread
# ---------------------------------------------------------
class TestPostDailyThread(unittest.TestCase):

    def setUp(self):
        """Setup: create mock app"""
        self.mock_app = MagicMock()
        self.mock_app.client.chat_postMessage.return_value = {"ts": "1234567890.123456"}
        bot_module.app = self.mock_app
        bot_module.CHANNEL_ID = 'C08UT7VP2TA'
        bot_module.daily_thread_ts = None

    @patch('main.get_vacation_users', return_value=set())
    def test_post_daily_thread_sends_message(self, mock_vacation):
        """TC-03-01: post_daily_thread() must send a message to the channel"""
        bot_module.post_daily_thread()
        # First call is the main standup message, second is vacation status
        self.assertTrue(self.mock_app.client.chat_postMessage.called)
        first_call_kwargs = self.mock_app.client.chat_postMessage.call_args_list[0][1]
        self.assertEqual(first_call_kwargs['channel'], 'C08UT7VP2TA')

    @patch('main.get_vacation_users', return_value=set())
    def test_post_daily_thread_uses_correct_channel(self, mock_vacation):
        """TC-03-02: post_daily_thread() must send to the correct channel"""
        bot_module.post_daily_thread()
        first_call_kwargs = self.mock_app.client.chat_postMessage.call_args_list[0][1]
        self.assertEqual(first_call_kwargs['channel'], 'C08UT7VP2TA')

    @patch('main.get_vacation_users', return_value=set())
    def test_post_daily_thread_sets_daily_thread_ts(self, mock_vacation):
        """TC-03-03: post_daily_thread() must save thread ts"""
        bot_module.post_daily_thread()
        self.assertIsNotNone(bot_module.daily_thread_ts)
        self.assertEqual(bot_module.daily_thread_ts, "1234567890.123456")

    @patch('main.get_vacation_users', return_value=set())
    def test_post_daily_thread_uses_opening_phrase(self, mock_vacation):
        """TC-03-04: post_daily_thread() must use a phrase from OPENING_PHRASES"""
        from phrases import OPENING_PHRASES
        bot_module.post_daily_thread()
        first_call_kwargs = self.mock_app.client.chat_postMessage.call_args_list[0][1]
        text = first_call_kwargs['text']
        self.assertTrue(
            any(text.startswith(phrase) for phrase in OPENING_PHRASES),
            f"Message text must start with one of OPENING_PHRASES"
        )

    @patch('main.get_vacation_users', return_value=set())
    def test_post_daily_thread_mentions_gtm_team(self, mock_vacation):
        """TC-03-06: Daily standup post mentions the GTM user group"""
        bot_module.post_daily_thread()
        text = self.mock_app.client.chat_postMessage.call_args_list[0][1]['text']
        self.assertIn("<!subteam^S0BHNJ7J12M>", text)

    def test_post_daily_thread_skips_if_no_app(self):
        """TC-03-07: post_daily_thread() must exit if app is not initialized"""
        bot_module.app = None
        bot_module.post_daily_thread()
        self.assertIsNone(bot_module.daily_thread_ts)

    def test_post_daily_thread_skips_if_no_channel(self):
        """TC-03-08: post_daily_thread() must exit if CHANNEL_ID is empty"""
        bot_module.app = self.mock_app
        bot_module.CHANNEL_ID = None
        bot_module.post_daily_thread()
        self.mock_app.client.chat_postMessage.assert_not_called()
        self.mock_app.client.files_upload_v2.assert_not_called()

    def test_post_daily_thread_handles_api_error(self):
        """TC-03-09: post_daily_thread() must handle API errors without crashing"""
        self.mock_app.client.chat_postMessage.side_effect = Exception("Slack API error")
        try:
            bot_module.post_daily_thread()
        except Exception:
            self.fail("post_daily_thread() must not raise exceptions")


# ---------------------------------------------------------
# TC-04: check_missing_reports
# ---------------------------------------------------------
class TestCheckMissingReports(unittest.TestCase):

    def setUp(self):
        self.mock_app = MagicMock()
        self.mock_supabase = MagicMock()
        bot_module.app = self.mock_app
        bot_module.supabase = self.mock_supabase
        bot_module.daily_thread_ts = "1234567890.123456"
        bot_module.CHANNEL_ID = 'C08UT7VP2TA'
        bot_module.TEAM_USER_IDS = ["U111", "U222"]

    def test_skip_if_no_daily_thread(self):
        """TC-04-01: check_missing_reports() skips if no daily thread"""
        bot_module.daily_thread_ts = None
        bot_module.check_missing_reports()
        self.mock_supabase.table.assert_not_called()

    def test_skip_if_no_supabase(self):
        """TC-04-02: check_missing_reports() skips if no supabase"""
        bot_module.supabase = None
        bot_module.check_missing_reports()
        self.assertIsNone(bot_module.supabase)

    @patch('main.get_vacation_users', return_value={"U222"})
    def test_excludes_users_on_vacation(self, mock_vacation):
        """TC-04-03: Vacation users are excluded from reminder targeting"""
        mock_response = MagicMock()
        mock_response.data = [{"user_id": "U111"}]
        self.mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_response

        bot_module.check_missing_reports()

        self.mock_app.client.chat_postMessage.assert_not_called()

    @patch('main.get_vacation_users', return_value=set())
    def test_pings_missing_users(self, mock_vacation):
        """TC-04-04: check_missing_reports() pings users who haven't reported"""
        # Only U111 has reported
        mock_response = MagicMock()
        mock_response.data = [{"user_id": "U111"}]
        self.mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_response

        bot_module.check_missing_reports()

        # Should upload the reminder for U222 into the active thread.
        self.mock_app.client.files_upload_v2.assert_called_once()
        call_kwargs = self.mock_app.client.files_upload_v2.call_args[1]
        self.assertIn("U222", call_kwargs['initial_comment'])
        self.assertEqual(call_kwargs['channel'], 'C08UT7VP2TA')
        self.assertEqual(call_kwargs['thread_ts'], "1234567890.123456")
        self.mock_app.client.chat_postMessage.assert_not_called()

    @patch('main.get_vacation_users', return_value=set())
    def test_no_ping_if_all_reported(self, mock_vacation):
        """TC-04-05: check_missing_reports() does not ping if everyone reported"""
        mock_response = MagicMock()
        mock_response.data = [{"user_id": "U111"}, {"user_id": "U222"}]
        self.mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_response

        bot_module.check_missing_reports()
        self.mock_app.client.chat_postMessage.assert_not_called()
        self.mock_app.client.files_upload_v2.assert_not_called()

    @patch('main.get_vacation_users', return_value=set())
    def test_pings_all_if_none_reported(self, mock_vacation):
        """TC-04-06: check_missing_reports() pings everyone if no one reported"""
        mock_response = MagicMock()
        mock_response.data = []
        self.mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_response

        bot_module.check_missing_reports()
        self.mock_app.client.files_upload_v2.assert_called_once()
        call_kwargs = self.mock_app.client.files_upload_v2.call_args[1]
        self.assertIn("U111", call_kwargs['initial_comment'])
        self.assertIn("U222", call_kwargs['initial_comment'])
        self.mock_app.client.chat_postMessage.assert_not_called()


class TestGetMissingUsersToday(unittest.TestCase):

    def setUp(self):
        self.mock_supabase = MagicMock()
        bot_module.supabase = self.mock_supabase
        bot_module.app = None
        bot_module.CHANNEL_ID = 'C08UT7VP2TA'
        bot_module.daily_thread_ts = None
        bot_module.TEAM_USER_IDS = ["U111", "U222", "U333"]

    @patch('main.get_vacation_users', return_value=set())
    def test_excludes_reported_users(self, mock_vacation):
        """TC-04H-01: Shared helper excludes already reported users"""
        mock_response = MagicMock()
        mock_response.data = [{"user_id": "U111"}]
        self.mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_response

        missing_users = bot_module.get_missing_users_today()

        self.assertEqual(missing_users, ["U222", "U333"])

    @patch('main.get_vacation_users', return_value=set())
    def test_excludes_users_seen_in_slack_thread_when_db_missed_event(self, mock_vacation):
        """TC-04H-01A: Slack thread history prevents false missing pings after missed events"""
        bot_module.app = MagicMock()
        bot_module.daily_thread_ts = "1234567890.123456"

        mock_response = MagicMock()
        mock_response.data = [{"user_id": "U111"}]
        self.mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_response
        bot_module.app.client.conversations_replies.return_value = {
            "messages": [
                {"user": "U0AGM4126DU", "bot_id": "B123", "ts": "1234567890.123456"},
                {
                    "user": "U222",
                    "text": "Yesterday: shipped X\nToday: ship Y",
                    "ts": "1234567891.000001",
                    "thread_ts": "1234567890.123456",
                },
            ],
            "has_more": False,
        }

        missing_users = bot_module.get_missing_users_today()

        self.assertEqual(missing_users, ["U333"])

    @patch('main.get_vacation_users', return_value={"U333"})
    def test_excludes_vacation_users(self, mock_vacation):
        """TC-04H-02: Shared helper excludes users on vacation"""
        mock_response = MagicMock()
        mock_response.data = [{"user_id": "U111"}]
        self.mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_response

        missing_users = bot_module.get_missing_users_today()

        self.assertEqual(missing_users, ["U222"])

    @patch('main.get_vacation_users', return_value="error")
    def test_treats_vacation_api_error_as_no_vacations(self, mock_vacation):
        """TC-04H-03: Shared helper treats vacation API errors as empty vacation set"""
        mock_response = MagicMock()
        mock_response.data = [{"user_id": "U111"}]
        self.mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_response

        missing_users = bot_module.get_missing_users_today()

        self.assertEqual(missing_users, ["U222", "U333"])


# ---------------------------------------------------------
# TC-05: handle_message_events (message handling in thread)
# ---------------------------------------------------------
class TestHandleMessageEvents(unittest.TestCase):

    def setUp(self):
        self.mock_app = MagicMock()
        self.mock_supabase = MagicMock()
        bot_module.app = self.mock_app
        bot_module.supabase = self.mock_supabase
        bot_module.daily_thread_ts = "1234567890.123456"
        bot_module.CHANNEL_ID = 'C08UT7VP2TA'

        # Register handler
        bot_module.register_events(self.mock_app)
        # Get the registered handler
        event_decorator = self.mock_app.event.return_value
        self.handler_func = event_decorator.call_args[0][0]

        # Mock the select->eq->eq chain to return no existing record
        self.mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(data=[])

    def _call_handler(self, body):
        """Helper method to call the handler"""
        logger = MagicMock()
        self.handler_func(body=body, logger=logger)

    def test_saves_report_to_supabase(self):
        """TC-05-01: Thread message is saved to Supabase"""
        body = {"event": {
            "user": "U999",
            "text": "Yesterday did X, today will do Y",
            "ts": "9999999999.000001",
            "thread_ts": "1234567890.123456",
        }}
        self._call_handler(body)
        self.mock_supabase.table.assert_called_with("standup_reports")
        insert_data = self.mock_supabase.table.return_value.insert.call_args[0][0]
        self.assertEqual(insert_data['user_id'], "U999")
        self.assertEqual(insert_data['raw_text'], "Yesterday did X, today will do Y")
        self.assertEqual(insert_data['date'], date.today().isoformat())

    @patch('main.random.choice', return_value='flow-state')
    def test_adds_random_approved_reaction_after_saving(self, mock_choice):
        """TC-05-02: An approved random reaction is added after saving"""
        body = {"event": {
            "user": "U999",
            "text": "My report",
            "ts": "9999999999.000001",
            "thread_ts": "1234567890.123456",
        }}
        self._call_handler(body)
        mock_choice.assert_called_once_with(bot_module.REACTION_ALIASES)
        self.mock_app.client.reactions_add.assert_called_once_with(
            channel='C08UT7VP2TA',
            name="flow-state",
            timestamp="9999999999.000001"
        )

    def test_random_reaction_selection_covers_all_approved_aliases(self):
        """TC-05-02A: Every approved alias can be selected for a saved report"""
        with patch('main.random.choice', side_effect=bot_module.REACTION_ALIASES) as mock_choice:
            for index, alias in enumerate(bot_module.REACTION_ALIASES):
                body = {"event": {
                    "user": "U999",
                    "text": f"Report {index}",
                    "ts": f"9999999999.000{index:03d}",
                    "thread_ts": "1234567890.123456",
                }}
                self._call_handler(body)

        self.assertEqual(mock_choice.call_count, 17)
        selected = [reaction_call.kwargs['name'] for reaction_call in self.mock_app.client.reactions_add.call_args_list]
        self.assertEqual(selected, list(bot_module.REACTION_ALIASES))

    def test_ignores_messages_outside_thread(self):
        """TC-05-03: Messages outside the thread are ignored"""
        body = {"event": {
            "user": "U999",
            "text": "Just a channel message",
            "ts": "9999999999.000001",
            "thread_ts": "9999111111.000000",  # different thread
        }}
        self._call_handler(body)
        self.mock_supabase.table.assert_not_called()

    def test_ignores_bot_messages(self):
        """TC-05-04: Bot messages are ignored"""
        body = {"event": {
            "user": "U999",
            "text": "Bot message",
            "ts": "9999999999.000001",
            "thread_ts": "1234567890.123456",
            "bot_id": "B123",
        }}
        self._call_handler(body)
        self.mock_supabase.table.assert_not_called()

    def test_ignores_if_no_daily_thread(self):
        """TC-05-05: If no active thread, all messages are ignored"""
        bot_module.daily_thread_ts = None
        body = {"event": {
            "user": "U999",
            "text": "A message",
            "ts": "9999999999.000001",
            "thread_ts": "1234567890.123456",
        }}
        self._call_handler(body)
        self.mock_supabase.table.assert_not_called()

    def test_handles_supabase_error_gracefully(self):
        """TC-05-06: Supabase error does not crash the handler"""
        self.mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.side_effect = Exception("DB error")
        body = {"event": {
            "user": "U999",
            "text": "My report",
            "ts": "9999999999.000001",
            "thread_ts": "1234567890.123456",
        }}
        try:
            self._call_handler(body)
        except Exception:
            self.fail("handle_message_events must not raise exceptions")

    def test_no_reaction_after_report_write_failure(self):
        """TC-05-07A: A failed report write is never confirmed with a reaction"""
        self.mock_supabase.table.return_value.insert.return_value.execute.side_effect = Exception("DB error")
        body = {"event": {
            "user": "U999",
            "text": "My report",
            "ts": "9999999999.000001",
            "thread_ts": "1234567890.123456",
        }}
        self._call_handler(body)
        self.mock_app.client.reactions_add.assert_not_called()

    def test_report_includes_thread_ts(self):
        """TC-05-07: Saved report contains the message thread_ts"""
        body = {"event": {
            "user": "U999",
            "text": "Report",
            "ts": "9999999999.000001",
            "thread_ts": "1234567890.123456",
        }}
        self._call_handler(body)
        insert_data = self.mock_supabase.table.return_value.insert.call_args[0][0]
        self.assertEqual(insert_data['thread_ts'], "9999999999.000001")


# ---------------------------------------------------------
# TC-06: phrases.py
# ---------------------------------------------------------
class TestPhrases(unittest.TestCase):

    def test_opening_phrases_not_empty(self):
        """TC-06-01: OPENING_PHRASES contains phrases"""
        from phrases import OPENING_PHRASES
        self.assertIsInstance(OPENING_PHRASES, list)
        self.assertGreater(len(OPENING_PHRASES), 0)

    def test_opening_phrases_are_strings(self):
        """TC-06-02: All phrases are strings"""
        from phrases import OPENING_PHRASES
        for phrase in OPENING_PHRASES:
            self.assertIsInstance(phrase, str)

    def test_opening_phrases_not_blank(self):
        """TC-06-03: All phrases are non-empty"""
        from phrases import OPENING_PHRASES
        for phrase in OPENING_PHRASES:
            self.assertTrue(len(phrase.strip()) > 0)

    def test_reaction_aliases_match_approved_manifest_aliases(self):
        """TC-06-04: Reaction aliases are exactly the approved 17 aliases"""
        expected = {
            "flow-state", "monkey-business", "investigating", "tired-monke",
            "together-4", "enough-for-today", "stop-nerding", "ship-smth",
            "mvp", "mvp-2", "together-3", "together-5", "pink-monke",
            "monkey-zen", "omg-monkey", "matrix-code", "matrix-monitors",
        }
        self.assertEqual(set(bot_module.REACTION_ALIASES), expected)
        self.assertEqual(len(bot_module.REACTION_ALIASES), 17)

    def test_media_aliases_are_manifest_backed_and_exclude_reaction_only_aliases(self):
        """TC-06-05: Media selection uses the 12 manifest assets with valid aliases"""
        manifest = json.loads(Path(bot_module.MEDIA_MANIFEST_PATH).read_text())
        self.assertEqual(set(bot_module.MEDIA_ALIASES), set(manifest))
        self.assertEqual(len(bot_module.MEDIA_ALIASES), 12)
        self.assertIn("ship-smth", bot_module.MEDIA_ALIASES)
        self.assertNotIn("ship", bot_module.MEDIA_ALIASES)
        self.assertTrue(
            {
                "pink-monke", "monkey-zen", "omg-monkey",
                "matrix-code", "matrix-monitors",
            }.isdisjoint(bot_module.MEDIA_ALIASES)
        )

    def test_opening_phrases_match_revised_copy(self):
        """TC-06-06: Opening phrases use the exact revised cool Slackbot copy"""
        from phrases import OPENING_PHRASES

        expected = [
            "Morning. Standup is open — keep it short, useful, and on the record.",
            "New day, same thread. What shipped, what is next, and what is in the way?",
            "Status window open. Facts first; side quests in subthreads.",
            "Standup is live. Drop the signal, skip the director's cut.",
            "Quick status check: done, next, blocked.",
            "The thread is live. Bring updates, not suspense.",
            "Morning sync starts here. If the plan changed, write it down.",
            "Standup is open. Keep it sharp and actionable.",
            "What shipped? What's next? What needs a hand?",
            "Daily status thread is live. Give us the useful version.",
            "No mystery, just status: yesterday, today, blockers.",
            "Status check-in is open. Concise is a feature.",
            "Thread unlocked. ETA changes and blockers belong here.",
            "Keep it factual, keep it moving, keep the blockers visible.",
            "13:00 is the deadline. The thread is the source of truth.",
            "One thread, three questions: yesterday, today, blockers.",
            "Standup is live. Keep the status here; move the debate to subthreads.",
            "Drop the update while it is still fresh.",
            "Monkey see, monkey do: make the status visible. 🐒",
            "Support your local monkey business: post the update before 13:00. 🐒",
            "Low battery, high signal. Drop the useful version.",
            "Case file open: what shipped, what is next, what is stuck?",
            "Ship check: what moved, what is next, what is stuck?",
            "Flow state starts with a clean status.",
            "Monkey business, minus the mystery.",
            "Need a quick win? Start with the status.",
        ]
        self.assertEqual(OPENING_PHRASES, expected)

    def test_reminder_and_thread_closed_copy_match_revised_proposal(self):
        """TC-06-07: Reminder and thread-closed copy uses exact revised strings"""
        self.assertEqual(bot_module.REMINDER_MESSAGES, (
            "Hey {MENTIONS} — your standup update is still missing. Reply in this thread with Yesterday, Today, and Blockers/Risks before 13:00.",
            "Hey {MENTIONS} — quick nudge: the thread is still waiting on Yesterday, Today, and Blockers/Risks. Please post before 13:00.",
            "Hey {MENTIONS} — no update from you yet. Add Yesterday, Today, and Blockers/Risks here before 13:00.",
            "Hey {MENTIONS} — the thread is missing your update. Keep it brief: Yesterday, Today, Blockers/Risks. Deadline: 13:00.",
            "Hey {MENTIONS} — make the status visible. Reply here with Yesterday, Today, and Blockers/Risks before 13:00. 🐒",
            "Hey {MENTIONS} — support your local monkey business and drop your update here before 13:00: Yesterday, Today, and Blockers/Risks.",
        ))
        self.assertEqual(bot_module.THREAD_CLOSED_MESSAGE, "DDL passed. Thread closed.")
        self.assertNotIn("tomorrow", bot_module.THREAD_CLOSED_MESSAGE.casefold())

    def test_refreshed_copy_avoids_repeated_or_corporate_wording(self):
        """TC-06-08: Runtime copy keeps the joke layer light and avoids stale wording."""
        source = "\n".join(
            (
                Path(bot_module.__file__).read_text(encoding="utf-8"),
                (Path(bot_module.__file__).parent / "phrases.py").read_text(encoding="utf-8"),
            )
        )
        self.assertNotIn("paper trail", source.casefold())
        self.assertNotIn("chaos organized", source.casefold())
        self.assertEqual(source.count("🐒"), 3)


# ---------------------------------------------------------
# TC-07: post_daily_thread — extended checks
# ---------------------------------------------------------
class TestPostDailyThreadExtended(unittest.TestCase):

    def setUp(self):
        self.mock_app = MagicMock()
        self.mock_app.client.chat_postMessage.return_value = {"ts": "1234567890.123456"}
        bot_module.app = self.mock_app
        bot_module.CHANNEL_ID = 'C08UT7VP2TA'
        bot_module.daily_thread_ts = None

    @patch('main.get_vacation_users', return_value=set())
    def test_standup_text_contains_instructions(self, mock_vacation):
        """TC-07-01: Message contains standup instructions"""
        bot_module.post_daily_thread()
        first_call_kwargs = self.mock_app.client.chat_postMessage.call_args_list[0][1]
        text = first_call_kwargs['text']
        self.assertIn("Yesterday", text)
        self.assertIn("Today", text)
        self.assertIn("Blockers", text)

    @patch('main.get_vacation_users', return_value=set())
    def test_standup_text_contains_thread_label(self, mock_vacation):
        """TC-07-02: Message contains Daily status thread label"""
        bot_module.post_daily_thread()
        first_call_kwargs = self.mock_app.client.chat_postMessage.call_args_list[0][1]
        self.assertIn("Daily", first_call_kwargs['text'])

    @patch('main.get_vacation_users', return_value=set())
    def test_standup_text_uses_exact_monkey_business_contract(self, mock_vacation):
        """TC-07-02A: Daily instructions and mentions use the approved copy"""
        bot_module.post_daily_thread()
        text = self.mock_app.client.chat_postMessage.call_args_list[0][1]['text']
        self.assertIn("*Daily status thread*", text)
        self.assertIn("*Reply in the active thread before 13:00 with:*", text)
        self.assertIn("*Yesterday:* what shipped or merged. If this continues yesterday's work, quote your previous update and add the current status.", text)
        self.assertIn("*Today:* what you will complete today and, if relevant, how many days remain.", text)
        self.assertIn("*Blockers / Risks:* who or what you need to unblock you.", text)
        self.assertIn("*Keep status in this thread; move discussions to subthreads.*", text)
        self.assertIn("*If something will not be finished today, state the remaining time.*", text)
        self.assertIn("<!subteam^S074DP77Q9H> <!subteam^S08EJBE5Q4X> <!subteam^S0BHNJ7J12M>", text)
        self.assertIn("cc: <@U068KKKNP9R>", text)

    @patch('main.get_opening_phrase', return_value="Status window open. Facts first; side quests in subthreads.")
    @patch('main.get_vacation_users', return_value=set())
    def test_standup_intro_has_one_fixed_banana_after_team_mentions(self, mock_vacation, mock_opening):
        """TC-07-02F: The opening post contains one predictable banana marker."""
        bot_module.post_daily_thread()
        text = self.mock_app.client.chat_postMessage.call_args_list[0][1]['text']
        self.assertEqual(text.count("🍌"), 1)
        self.assertIn(
            "<!subteam^S074DP77Q9H> <!subteam^S08EJBE5Q4X> <!subteam^S0BHNJ7J12M> 🍌",
            text,
        )

    @patch('main.get_vacation_users', return_value="error")
    def test_vacation_unavailable_uses_revised_copy(self, mock_vacation):
        """TC-07-02B: Vacation Tracker failure uses the approved status copy"""
        bot_module.post_daily_thread()
        self.assertEqual(
            self.mock_app.client.chat_postMessage.call_args_list[1][1]['text'],
            "⚠️ _Vacation Tracker is unavailable, so today's leave status is unknown. Monkey Business continues, but we will not guess who is out._",
        )

    @patch('main.get_vacation_users', return_value={"U111"})
    def test_vacation_users_use_revised_copy(self, mock_vacation):
        """TC-07-02C: Vacation mentions use the approved status copy"""
        bot_module.post_daily_thread()
        self.assertEqual(
            self.mock_app.client.chat_postMessage.call_args_list[1][1]['text'],
            "🌴 *Out today — confirmed by Vacation Tracker:* <@U111>\nEnjoy the PTO. We'll keep the status thread moving.",
        )

    @patch('main.get_vacation_users', return_value=set())
    def test_no_vacation_users_use_revised_copy(self, mock_vacation):
        """TC-07-02D: Full-team vacation status uses the approved copy"""
        bot_module.post_daily_thread()
        self.assertEqual(
            self.mock_app.client.chat_postMessage.call_args_list[1][1]['text'],
            "*Full team today:* Vacation Tracker reports no absences. Let's keep the status moving.",
        )

    @patch('main.send_alert')
    @patch('main.get_vacation_users', return_value=set())
    def test_daily_thread_alert_uses_revised_copy(self, mock_vacation, mock_alert):
        """TC-07-02E: Daily-thread alert uses the approved copy"""
        bot_module.post_daily_thread()
        mock_alert.assert_called_once_with(
            "Today's standup thread is live: <https://slack.com/archives/C08UT7VP2TA/p1234567890123456|open the active thread>"
        )

    @patch('main.get_vacation_users', return_value=set())
    def test_post_daily_thread_persists_state_to_supabase(self, mock_vacation):
        """TC-07-03: post_daily_thread() saves ts to bot_state table"""
        mock_supabase = MagicMock()
        bot_module.supabase = mock_supabase
        bot_module.post_daily_thread()
        mock_supabase.table.assert_called_with("bot_state")
        upsert_data = mock_supabase.table.return_value.upsert.call_args[0][0]
        self.assertEqual(upsert_data['key'], 'daily_thread_ts')
        self.assertEqual(upsert_data['value'], '1234567890.123456')
        bot_module.supabase = None

    @patch('main.get_vacation_users', return_value=set())
    def test_post_daily_thread_handles_supabase_state_error(self, mock_vacation):
        """TC-07-04: bot_state save error does not crash the bot"""
        mock_supabase = MagicMock()
        mock_supabase.table.return_value.upsert.return_value.execute.side_effect = Exception("DB error")
        bot_module.supabase = mock_supabase
        try:
            bot_module.post_daily_thread()
        except Exception:
            self.fail("bot_state error must not crash post_daily_thread")
        # Thread should still be created
        self.assertEqual(bot_module.daily_thread_ts, "1234567890.123456")
        bot_module.supabase = None


# ---------------------------------------------------------
# TC-08: check_missing_reports — extended checks
# ---------------------------------------------------------
class TestCheckMissingReportsExtended(unittest.TestCase):

    def setUp(self):
        self.mock_app = MagicMock()
        self.mock_supabase = MagicMock()
        bot_module.app = self.mock_app
        bot_module.supabase = self.mock_supabase
        bot_module.daily_thread_ts = "1234567890.123456"
        bot_module.CHANNEL_ID = 'C08UT7VP2TA'
        bot_module.TEAM_USER_IDS = ["U111", "U222", "U333"]

    @patch('main.random.choice', side_effect=[bot_module.REMINDER_MESSAGES[0], "flow-state"])
    @patch('main.get_vacation_users', return_value=set())
    def test_reminder_message_is_concise_and_actionable(self, mock_vacation, mock_choice):
        """TC-08-01: Reminder is concise, actionable, and deadline-aware"""
        mock_response = MagicMock()
        mock_response.data = []
        self.mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_response
        bot_module.check_missing_reports()
        call_kwargs = self.mock_app.client.files_upload_v2.call_args[1]
        reminder_text = call_kwargs['initial_comment']
        self.assertIn("Yesterday, Today, and Blockers/Risks", reminder_text)
        self.assertIn("before 13:00", reminder_text)
        self.assertNotIn("paper trail", reminder_text.casefold())

    @patch('main.get_vacation_users', return_value=set())
    def test_reminder_sent_in_thread(self, mock_vacation):
        """TC-08-02: Reminder is sent in thread, not in channel"""
        mock_response = MagicMock()
        mock_response.data = []
        self.mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_response
        bot_module.check_missing_reports()
        self.mock_app.client.files_upload_v2.assert_called_once()
        call_kwargs = self.mock_app.client.files_upload_v2.call_args[1]
        self.assertEqual(call_kwargs['channel'], 'C08UT7VP2TA')
        self.assertEqual(call_kwargs['thread_ts'], "1234567890.123456")
        reminder_text = call_kwargs['initial_comment']
        self.assertIn("Yesterday, Today", reminder_text)
        self.assertIn("Blockers/Risks", reminder_text)

    @patch('main.send_alert')
    @patch('main.random.choice', side_effect=[bot_module.REMINDER_MESSAGES[0], "flow-state"])
    @patch('main.get_vacation_users', return_value=set())
    def test_reminder_uses_separate_media_alias_selection(self, mock_vacation, mock_choice, mock_alert):
        """TC-08-02A: Reminder media selection is separate from reaction-only aliases"""
        mock_response = MagicMock()
        mock_response.data = []
        self.mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_response

        bot_module.check_missing_reports()

        mock_choice.assert_has_calls([
            call(bot_module.REMINDER_MESSAGES),
            call(bot_module.MEDIA_ALIASES),
        ])
        self.mock_app.client.files_upload_v2.assert_called_once()
        self.assertEqual(
            mock_alert.call_args.args[0],
            "Standup reminder sent to 3 missing reporter(s).",
        )

    @patch('main.send_alert')
    @patch('main.get_vacation_users', return_value=set())
    def test_all_reports_alert_uses_revised_copy(self, mock_vacation, mock_alert):
        """TC-08-02B: All-reports alert uses the approved copy"""
        mock_response = MagicMock()
        mock_response.data = [
            {"user_id": "U111"},
            {"user_id": "U222"},
            {"user_id": "U333"},
        ]
        self.mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_response

        bot_module.check_missing_reports()

        mock_alert.assert_called_once_with("All standup reports are in. The status thread is complete.")

    def test_handles_supabase_error_gracefully(self):
        """TC-08-03: Supabase error in check_missing_reports does not crash"""
        self.mock_supabase.table.return_value.select.return_value.eq.return_value.execute.side_effect = Exception("DB error")
        try:
            bot_module.check_missing_reports()
        except Exception:
            self.fail("check_missing_reports must not raise exceptions on DB error")

    @patch('main.get_vacation_users', return_value=set())
    def test_queries_today_date(self, mock_vacation):
        """TC-08-04: Supabase query uses today's date"""
        mock_response = MagicMock()
        mock_response.data = [{"user_id": "U111"}, {"user_id": "U222"}, {"user_id": "U333"}]
        self.mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_response
        bot_module.check_missing_reports()
        eq_call = self.mock_supabase.table.return_value.select.return_value.eq.call_args
        self.assertEqual(eq_call[0][0], "date")
        self.assertEqual(eq_call[0][1], date.today().isoformat())


class TestNotificationAssets(unittest.TestCase):

    ROOT = Path(__file__).resolve().parent

    def test_all_manifest_assets_exist_and_have_no_runtime_mp4(self):
        """TC-08-05: Every manifest asset exists and runtime paths are GIF/PNG only."""
        manifest_path = self.ROOT / "assets" / "monkey-business" / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        self.assertEqual(set(manifest), set(bot_module.MEDIA_ALIASES))
        for entry in manifest.values():
            asset_path = self.ROOT / entry['path']
            self.assertTrue(asset_path.is_file(), asset_path)
            self.assertNotEqual(asset_path.suffix.lower(), ".mp4")
            self.assertIn(entry['media_type'], {"image/gif", "image/png"})

    def test_giphy_and_old_reaction_behavior_are_removed(self):
        """TC-08-06: Production runtime contains no Giphy or blue-heart flow."""
        source = (self.ROOT / "main.py").read_text().lower()
        self.assertNotIn("giphy", source)
        self.assertNotIn("blue_heart", source)
        self.assertNotIn("reminder_memes", source)
        self.assertNotIn("end_of_day_gifs", source)

    def test_docker_image_copies_runtime_assets(self):
        """TC-08-07: The Docker image includes the local media directory."""
        dockerfile = (self.ROOT / "Dockerfile").read_text()
        self.assertIn("COPY assets/monkey-business ./assets/monkey-business", dockerfile)

    def test_docker_context_keeps_media_manifest(self):
        """TC-08-08: The Docker context does not exclude the runtime manifest."""
        dockerignore = (self.ROOT / ".dockerignore").read_text()
        self.assertIn("!assets/monkey-business/manifest.json", dockerignore)

    def test_rejected_identity_and_banana_copy_are_absent_from_project_files(self):
        """TC-08-09: Rejected identity and banana copy are absent from project-facing files."""
        project_files = (
            "main.py",
            "phrases.py",
            "AGENTS.md",
            "CLAUDE.md",
            "DEPLOY.md",
            "MANIFEST.md",
        )
        source = "\n".join((self.ROOT / path).read_text() for path in project_files).lower()
        self.assertNotIn("gnik gnok", source)
        self.assertNotIn("monkey scott", source)
        self.assertNotIn("banana", source)


class TestEndOfDayEscalation(unittest.TestCase):

    def setUp(self):
        self.mock_app = MagicMock()
        self.mock_supabase = MagicMock()
        bot_module.app = self.mock_app
        bot_module.supabase = self.mock_supabase
        bot_module.daily_thread_ts = "1234567890.123456"
        bot_module.CHANNEL_ID = 'C08UT7VP2TA'
        bot_module.TEAM_USER_IDS = ["U111", "U222", "U333"]

    @patch('main.random.choice', return_value="mvp")
    @patch('main.get_vacation_users', return_value=set())
    def test_posts_when_users_are_missing(self, mock_vacation, mock_choice):
        """TC-08E-01: End-of-day escalation posts when users are still missing"""
        mock_response = MagicMock()
        mock_response.data = [{"user_id": "U111"}]
        self.mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_response

        bot_module.post_end_of_day_escalation()

        self.mock_app.client.files_upload_v2.assert_called_once()
        call_kwargs = self.mock_app.client.files_upload_v2.call_args[1]
        self.assertEqual(call_kwargs['channel'], 'C08UT7VP2TA')
        self.assertEqual(call_kwargs['thread_ts'], "1234567890.123456")
        self.assertEqual(call_kwargs['file'], str(Path(bot_module.__file__).parent / "assets/monkey-business/mvp.gif"))
        self.assertEqual(
            call_kwargs['initial_comment'],
            "End-of-day check: <@U222> <@U333> still have no update in the active thread. "
            "<@U068KKKNP9R>, please take a look.",
        )

    @patch('main.random.choice', return_value="mvp")
    @patch('main.get_vacation_users', return_value=set())
    def test_upload_failure_falls_back_to_text_only_thread_message(self, mock_vacation, mock_choice):
        """TC-08E-01A: Escalation upload failure preserves text in the same thread."""
        mock_response = MagicMock()
        mock_response.data = [{"user_id": "U111"}]
        self.mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_response
        self.mock_app.client.files_upload_v2.side_effect = Exception("files:write unavailable")

        bot_module.post_end_of_day_escalation()

        self.mock_app.client.chat_postMessage.assert_called_once_with(
            channel='C08UT7VP2TA',
            thread_ts="1234567890.123456",
            text=(
                "End-of-day check: <@U222> <@U333> still have no update in the active thread. "
                "<@U068KKKNP9R>, please take a look."
            ),
        )

    @patch('main.get_vacation_users', return_value=set())
    def test_does_nothing_when_no_one_is_missing(self, mock_vacation):
        """TC-08E-02: End-of-day escalation stays silent when everyone reported"""
        mock_response = MagicMock()
        mock_response.data = [{"user_id": "U111"}, {"user_id": "U222"}, {"user_id": "U333"}]
        self.mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_response

        bot_module.post_end_of_day_escalation()

        self.mock_app.client.chat_postMessage.assert_not_called()
        self.mock_app.client.files_upload_v2.assert_not_called()

    def test_does_nothing_without_daily_thread(self):
        """TC-08E-03: End-of-day escalation skips without daily thread"""
        bot_module.daily_thread_ts = None

        bot_module.post_end_of_day_escalation()

        self.mock_supabase.table.assert_not_called()
        self.mock_app.client.chat_postMessage.assert_not_called()

    def test_does_nothing_without_supabase(self):
        """TC-08E-04: End-of-day escalation skips without Supabase"""
        bot_module.supabase = None

        bot_module.post_end_of_day_escalation()

        self.mock_app.client.chat_postMessage.assert_not_called()


# ---------------------------------------------------------
# TC-09: handle_message_events — edge cases
# ---------------------------------------------------------
class TestHandleMessageEdgeCases(unittest.TestCase):

    def setUp(self):
        self.mock_app = MagicMock()
        self.mock_supabase = MagicMock()
        bot_module.app = self.mock_app
        bot_module.supabase = self.mock_supabase
        bot_module.daily_thread_ts = "1234567890.123456"
        bot_module.CHANNEL_ID = 'C08UT7VP2TA'

        bot_module.register_events(self.mock_app)
        event_decorator = self.mock_app.event.return_value
        self.handler_func = event_decorator.call_args[0][0]

        # Mock the select->eq->eq chain to return no existing record
        self.mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(data=[])

    def _call_handler(self, body):
        logger = MagicMock()
        self.handler_func(body=body, logger=logger)

    def test_ignores_message_without_thread_ts(self):
        """TC-09-01: Message without thread_ts (not in thread) is ignored"""
        body = {"event": {
            "user": "U999",
            "text": "Regular message",
            "ts": "9999999999.000001",
        }}
        self._call_handler(body)
        self.mock_supabase.table.assert_not_called()

    def test_no_supabase_still_no_crash(self):
        """TC-09-02: Thread message without supabase does not crash"""
        bot_module.supabase = None
        body = {"event": {
            "user": "U999",
            "text": "Report",
            "ts": "9999999999.000001",
            "thread_ts": "1234567890.123456",
        }}
        try:
            self._call_handler(body)
        except Exception:
            self.fail("Must not crash without supabase")
        bot_module.supabase = self.mock_supabase

    def test_reaction_not_added_on_supabase_error(self):
        """TC-09-03: On Supabase error, reaction is not added (don't confirm unsaved data)"""
        # Make the select->eq->eq chain raise an error (this is the first DB call in the handler)
        self.mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.side_effect = Exception("DB error")
        body = {"event": {
            "user": "U999",
            "text": "My report",
            "ts": "9999999999.000001",
            "thread_ts": "1234567890.123456",
        }}
        self._call_handler(body)
        # Reaction should not be added if the DB call failed
        self.mock_app.client.reactions_add.assert_not_called()


# ---------------------------------------------------------
# TC-10: main() — initialization
# ---------------------------------------------------------
class TestMainFunction(unittest.TestCase):

    @patch('main.SocketModeHandler')
    @patch('main.App')
    @patch('main.BackgroundScheduler')
    @patch('main.get_supabase_client')
    def test_main_exits_without_tokens(self, mock_supa, mock_sched, mock_app, mock_handler):
        """TC-10-01: main() does not start without tokens"""
        original_bot = bot_module.SLACK_BOT_TOKEN
        original_app = bot_module.SLACK_APP_TOKEN
        bot_module.SLACK_BOT_TOKEN = None
        bot_module.SLACK_APP_TOKEN = None
        bot_module.main()
        mock_app.assert_not_called()
        bot_module.SLACK_BOT_TOKEN = original_bot
        bot_module.SLACK_APP_TOKEN = original_app

    @patch('main.SocketModeHandler')
    @patch('main.App')
    @patch('main.BackgroundScheduler')
    @patch('main.get_supabase_client')
    def test_main_initializes_app(self, mock_supa, mock_sched, mock_app_cls, mock_handler):
        """TC-10-02: main() initializes App with token"""
        bot_module.SLACK_BOT_TOKEN = 'xoxb-test'
        bot_module.SLACK_APP_TOKEN = 'xapp-test'
        mock_app_instance = MagicMock()
        mock_app_cls.return_value = mock_app_instance
        mock_supa.return_value = MagicMock()
        # Mock the test block
        mock_app_instance.client.chat_postMessage.return_value = {"ts": "123"}
        bot_module.main()
        mock_app_cls.assert_called_once_with(token='xoxb-test')

    @patch('main.SocketModeHandler')
    @patch('main.App')
    @patch('main.BackgroundScheduler')
    @patch('main.get_supabase_client')
    def test_main_schedules_jobs(self, mock_supa, mock_sched_cls, mock_app_cls, mock_handler):
        """TC-10-03: main() registers jobs in the scheduler"""
        bot_module.SLACK_BOT_TOKEN = 'xoxb-test'
        bot_module.SLACK_APP_TOKEN = 'xapp-test'
        mock_sched = MagicMock()
        mock_sched_cls.return_value = mock_sched
        mock_app = MagicMock()
        mock_app_cls.return_value = mock_app
        mock_supa.return_value = MagicMock()
        mock_app.client.chat_postMessage.return_value = {"ts": "123"}
        bot_module.main()
        mock_sched_cls.assert_called_once_with(timezone=bot_module.LOCAL_TIMEZONE)
        self.assertEqual(mock_sched.add_job.call_count, 5)
        add_job_calls = mock_sched.add_job.call_args_list
        self.assertEqual(add_job_calls[0][0][0], bot_module.post_daily_thread)
        self.assertEqual(add_job_calls[0][1]['hour'], 9)
        self.assertEqual(add_job_calls[1][0][0], bot_module.send_personal_standup_reminder)
        self.assertEqual(add_job_calls[1][1]['hour'], 9)
        self.assertEqual(add_job_calls[1][1]['minute'], 15)
        self.assertEqual(add_job_calls[2][0][0], bot_module.check_missing_reports)
        self.assertEqual(add_job_calls[2][1]['hour'], 12)
        self.assertEqual(add_job_calls[2][1]['minute'], 30)
        self.assertEqual(add_job_calls[3][0][0], bot_module.post_thread_closed)
        self.assertEqual(add_job_calls[3][1]['hour'], 13)
        self.assertEqual(add_job_calls[3][1]['minute'], 1)
        self.assertEqual(add_job_calls[4][0][0], bot_module.post_end_of_day_escalation)
        self.assertEqual(add_job_calls[4][1]['hour'], 21)
        mock_sched.start.assert_called_once()


# ---------------------------------------------------------
# TC-11: get_vacation_users — Vacation Tracker API
# ---------------------------------------------------------
class TestGetVacationUsers(unittest.TestCase):

    def setUp(self):
        self.original_api_key = bot_module.VACATION_TRACKER_API_KEY
        bot_module.VACATION_TRACKER_API_KEY = "test-api-key"

    def tearDown(self):
        bot_module.VACATION_TRACKER_API_KEY = self.original_api_key

    @patch('main.requests.get')
    def test_returns_empty_set_without_api_key(self, mock_get):
        """TC-11-01: Returns empty set when API key is not configured"""
        bot_module.VACATION_TRACKER_API_KEY = None
        result = bot_module.get_vacation_users()
        self.assertEqual(result, set())
        mock_get.assert_not_called()

    @patch('main.requests.get')
    def test_finds_vacationers_from_api(self, mock_get):
        """TC-11-02: Correctly identifies team members on vacation"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "ok",
            "nextToken": None,
            "data": [
                {
                    "id": "leave-1",
                    "userId": "vt-user-1",
                    "status": "APPROVED",
                    "startDate": "2026-02-26",
                    "endDate": "2026-02-27",
                    "user": {"name": "Different Display Name", "email": "tapoton@replika.ai"},
                },
                {
                    "id": "leave-2",
                    "userId": "vt-user-2",
                    "status": "APPROVED",
                    "startDate": "2026-02-26",
                    "endDate": "2026-02-28",
                    "user": {"name": "Sergei Mironov"},
                },
            ],
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = bot_module.get_vacation_users()

        self.assertIn("U035U3KTFL5", result)  # Anton Tyutin
        self.assertIn("U04SBH53P9C", result)  # Sergei Mironov
        self.assertEqual(len(result), 2)

    @patch('main.requests.get')
    def test_ignores_non_approved_leaves(self, mock_get):
        """TC-11-03: Only approved leaves are counted"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "ok",
            "nextToken": None,
            "data": [
                {
                    "id": "leave-1",
                    "status": "APPROVED",
                    "user": {"name": "Anton Tyutin"},
                },
                {
                    "id": "leave-2",
                    "status": "PENDING",
                    "user": {"name": "Sergei Mironov"},
                },
                {
                    "id": "leave-3",
                    "status": "DENIED",
                    "user": {"name": "eddy"},
                },
            ],
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = bot_module.get_vacation_users()

        self.assertIn("U035U3KTFL5", result)  # Anton — APPROVED
        self.assertNotIn("U04SBH53P9C", result)  # Sergei — PENDING
        self.assertNotIn("U085J8B5TJ6", result)  # Ed — DENIED
        self.assertEqual(len(result), 1)

    @patch('main.requests.get')
    def test_handles_pagination(self, mock_get):
        """TC-11-04: Follows nextToken for paginated results"""
        page1 = MagicMock()
        page1.status_code = 200
        page1.json.return_value = {
            "status": "ok",
            "nextToken": "page2token",
            "data": [{"id": "l1", "status": "APPROVED", "user": {"name": "Anton Tyutin"}}],
        }
        page1.raise_for_status = MagicMock()

        page2 = MagicMock()
        page2.status_code = 200
        page2.json.return_value = {
            "status": "ok",
            "nextToken": None,
            "data": [{"id": "l2", "status": "APPROVED", "user": {"name": "eddy"}}],
        }
        page2.raise_for_status = MagicMock()

        mock_get.side_effect = [page1, page2]

        result = bot_module.get_vacation_users()

        self.assertEqual(mock_get.call_count, 2)
        self.assertIn("U035U3KTFL5", result)  # Anton
        self.assertIn("U085J8B5TJ6", result)  # eddy

    @patch('main.requests.get')
    def test_matches_vacationers_by_email_before_name(self, mock_get):
        """TC-11-04A: Email matching handles Vacation Tracker display-name drift"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "ok",
            "nextToken": None,
            "data": [
                {
                    "id": "leave-1",
                    "status": "APPROVED",
                    "user": {"name": "artem", "email": "artiom@replika.com"},
                },
                {
                    "id": "leave-2",
                    "status": "APPROVED",
                    "user": {"name": "ed", "email": "ed@replika.ai"},
                },
            ],
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = bot_module.get_vacation_users()

        self.assertIn("U07SR89J8NA", result)  # artiom
        self.assertIn("U085J8B5TJ6", result)  # eddy

    @patch('main.requests.get')
    def test_matches_vacationers_by_vacation_tracker_user_id_first(self, mock_get):
        """TC-11-04B: Vacation Tracker user IDs survive display-name and email changes"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "ok",
            "nextToken": None,
            "data": [
                {
                    "id": "leave-1",
                    "userId": "slack-986ddb5f-8fca-4fba-bb75-94c26a22afb7",
                    "status": "APPROVED",
                    "user": {"name": "Giorgio", "email": ""},
                },
                {
                    "id": "leave-2",
                    "status": "APPROVED",
                    "user": {
                        "id": "slack-720b8eaa-3d39-4bcd-9d96-57081203ab2d",
                        "name": "Pawel Changed",
                        "email": "changed@example.com",
                    },
                },
            ],
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = bot_module.get_vacation_users()

        self.assertIn("U09QE0E0HHQ", result)  # Giorgio
        self.assertIn("U08EFQCMJ3U", result)  # Pawel

    @patch('main.requests.get')
    def test_returns_error_on_http_failure(self, mock_get):
        """TC-11-05: Returns 'error' on API HTTP errors"""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        http_error = bot_module.requests.exceptions.HTTPError(response=mock_response)
        mock_response.raise_for_status.side_effect = http_error
        mock_get.return_value = mock_response

        result = bot_module.get_vacation_users()
        self.assertEqual(result, "error")

    @patch('main.requests.get')
    def test_returns_error_on_network_failure(self, mock_get):
        """TC-11-06: Returns 'error' on network errors"""
        mock_get.side_effect = Exception("Connection refused")

        result = bot_module.get_vacation_users()
        self.assertEqual(result, "error")

    @patch('main.requests.get')
    def test_sends_correct_headers_and_params(self, mock_get):
        """TC-11-07: Sends correct API key header and date params"""
        mock_response = MagicMock()
        mock_response.json.return_value = {"status": "ok", "data": [], "nextToken": None}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        bot_module.get_vacation_users()

        mock_get.assert_called_once()
        call_kwargs = mock_get.call_args[1]
        self.assertEqual(call_kwargs['headers']['x-api-key'], 'test-api-key')
        self.assertEqual(call_kwargs['params']['startDate'], date.today().isoformat())
        self.assertEqual(call_kwargs['params']['endDate'], date.today().isoformat())
        self.assertEqual(call_kwargs['params']['status'], 'APPROVED')
        self.assertEqual(call_kwargs['params']['expand'], 'user')
        self.assertEqual(call_kwargs['timeout'], 10)

    @patch('main.requests.get')
    def test_ignores_unknown_users(self, mock_get):
        """TC-11-08: Users not in TEAM_MAPPING are silently skipped"""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "status": "ok",
            "nextToken": None,
            "data": [
                {"id": "l1", "status": "APPROVED", "user": {"name": "Unknown Person"}},
                {"id": "l2", "status": "APPROVED", "user": {"name": "Anton Tyutin"}},
            ],
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = bot_module.get_vacation_users()

        self.assertEqual(len(result), 1)
        self.assertIn("U035U3KTFL5", result)  # Only Anton

    @patch('main.requests.get')
    def test_excludes_deactivated_users_from_vacation_results(self, mock_get):
        """TC-11-09: Deactivated users are excluded even with stale identity mappings"""
        original_mapping = bot_module.TEAM_MAPPING
        bot_module.TEAM_MAPPING = {
            **original_mapping,
            "U097GKF641M": {
                "vt_user_id": "slack-cristian-id",
                "name": "Cristian Matzov",
                "email": "cristian@example.com",
            },
        }

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "status": "ok",
            "nextToken": None,
            "data": [
                {
                    "id": "leave-cristian",
                    "userId": "slack-cristian-id",
                    "status": "APPROVED",
                    "user": {"name": "Cristian Matzov"},
                },
            ],
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        try:
            result = bot_module.get_vacation_users()
        finally:
            bot_module.TEAM_MAPPING = original_mapping

        self.assertNotIn("U097GKF641M", result)


# ---------------------------------------------------------
# TC-13: send_deploy_notification()
# ---------------------------------------------------------
class TestSendDeployNotification(unittest.TestCase):

    def setUp(self):
        self.mock_app = MagicMock()
        bot_module.app = self.mock_app
        bot_module.ALERT_CHANNEL_ID = 'C_ALERT'

    def test_sends_message_when_deploy_notify_set(self):
        """TC-13-01: send_deploy_notification() sends to ALERT_CHANNEL_ID when DEPLOY_NOTIFY=1"""
        with patch.dict('os.environ', {'DEPLOY_NOTIFY': '1'}):
            bot_module.send_deploy_notification()
        self.mock_app.client.chat_postMessage.assert_called_once()
        call_kwargs = self.mock_app.client.chat_postMessage.call_args[1]
        self.assertEqual(call_kwargs['channel'], 'C_ALERT')
        self.assertEqual(
            call_kwargs['text'],
            "🚀 Standup bot is back online.\nMode: *Standup collection*.",
        )

    def test_skips_when_deploy_notify_not_set(self):
        """TC-13-02: send_deploy_notification() does nothing without DEPLOY_NOTIFY=1"""
        env = {k: v for k, v in os.environ.items() if k != 'DEPLOY_NOTIFY'}
        with patch.dict('os.environ', env, clear=True):
            bot_module.send_deploy_notification()
        self.mock_app.client.chat_postMessage.assert_not_called()

    def test_skips_when_deploy_notify_wrong_value(self):
        """TC-13-03: send_deploy_notification() does nothing when DEPLOY_NOTIFY != '1'"""
        with patch.dict('os.environ', {'DEPLOY_NOTIFY': 'true'}):
            bot_module.send_deploy_notification()
        self.mock_app.client.chat_postMessage.assert_not_called()

    def test_no_crash_without_alert_channel(self):
        """TC-13-04: send_deploy_notification() does not crash if ALERT_CHANNEL_ID is not set"""
        bot_module.ALERT_CHANNEL_ID = None
        with patch.dict('os.environ', {'DEPLOY_NOTIFY': '1'}):
            try:
                bot_module.send_deploy_notification()
            except Exception:
                self.fail("must not raise when ALERT_CHANNEL_ID is None")

    def test_no_crash_without_app(self):
        """TC-13-05: send_deploy_notification() does not crash if app is not initialized"""
        bot_module.app = None
        with patch.dict('os.environ', {'DEPLOY_NOTIFY': '1'}):
            try:
                bot_module.send_deploy_notification()
            except Exception:
                self.fail("must not raise when app is None")


# ---------------------------------------------------------
# TC-12: Michael Scott motivational boost
# ---------------------------------------------------------
class TestThreadBoostsRemoved(unittest.TestCase):

    def setUp(self):
        self.mock_app = MagicMock()
        self.mock_supabase = MagicMock()
        bot_module.app = self.mock_app
        bot_module.supabase = self.mock_supabase
        bot_module.daily_thread_ts = "1234567890.123456"
        bot_module.CHANNEL_ID = 'C08UT7VP2TA'

        # Mock DB: no existing record
        self.mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(data=[])

        bot_module.register_events(self.mock_app)
        event_decorator = self.mock_app.event.return_value
        self.handler_func = event_decorator.call_args[0][0]

    def _call_handler(self, body):
        self.handler_func(body=body, logger=MagicMock())

    def _standup_body(self):
        return {"event": {
            "user": "U999",
            "text": "Yesterday: done X. Today: Y",
            "ts": "9999999999.000001",
            "thread_ts": "1234567890.123456",
        }}

    def test_thread_reply_does_not_send_extra_boost_messages(self):
        """TC-12-01: Standup replies do not trigger random extra thread messages"""
        self._call_handler(self._standup_body())
        self.mock_app.client.chat_postMessage.assert_not_called()

    @patch('main.random.choice', return_value='flow-state')
    def test_thread_reply_still_gets_confirmation_reaction(self, mock_choice):
        """TC-12-02: Standup replies still get the confirmation reaction"""
        self._call_handler(self._standup_body())
        self.mock_app.client.reactions_add.assert_called_once_with(
            channel='C08UT7VP2TA',
            name="flow-state",
            timestamp="9999999999.000001"
        )


# ---------------------------------------------------------
# TC-14: send_personal_standup_reminder()
# ---------------------------------------------------------
class TestPersonalStandupReminder(unittest.TestCase):

    def setUp(self):
        self.mock_app = MagicMock()
        self.mock_supabase = MagicMock()
        bot_module.app = self.mock_app
        bot_module.supabase = self.mock_supabase
        bot_module.daily_thread_ts = "1234567890.123456"
        bot_module.CHANNEL_ID = 'C08UT7VP2TA'
        bot_module.PERSONAL_REMINDER_USER_ID = 'U0821BRMJ4R'

        # Default: not posted today
        self.mock_supabase.table.return_value.select.return_value \
            .eq.return_value.eq.return_value.execute.return_value = MagicMock(data=[])

    def tearDown(self):
        bot_module.PERSONAL_REMINDER_USER_ID = ''

    def _set_today_report(self, exists: bool):
        self.mock_supabase.table.return_value.select.return_value \
            .eq.return_value.eq.return_value.execute.return_value = MagicMock(
                data=[{"user_id": "U0821BRMJ4R"}] if exists else []
            )

    def _set_prev_report(self, raw_text: str | None):
        """Patch supabase so the second call (prev workday lookup) returns raw_text."""
        today_response = MagicMock(data=[])
        prev_response = MagicMock(data=[{"raw_text": raw_text}] if raw_text is not None else [])

        self.mock_supabase.table.return_value.select.return_value \
            .eq.return_value.eq.return_value.execute.side_effect = [today_response, prev_response]

    def test_skips_when_no_user_id_configured(self):
        """TC-14-01: Does nothing when PERSONAL_REMINDER_USER_ID is empty."""
        bot_module.PERSONAL_REMINDER_USER_ID = ''
        bot_module.send_personal_standup_reminder()
        self.mock_app.client.chat_postMessage.assert_not_called()

    def test_skips_when_already_posted_today(self):
        """TC-14-02: No DM if user already posted today."""
        self.mock_supabase.table.return_value.select.return_value \
            .eq.return_value.eq.return_value.execute.return_value = MagicMock(
                data=[{"user_id": "U0821BRMJ4R"}]
            )
        bot_module.send_personal_standup_reminder()
        self.mock_app.client.chat_postMessage.assert_not_called()

    def test_skips_when_no_previous_report(self):
        """TC-14-03: No DM if no previous workday report found."""
        today_response = MagicMock(data=[])
        prev_response = MagicMock(data=[])
        self.mock_supabase.table.return_value.select.return_value \
            .eq.return_value.eq.return_value.execute.side_effect = [today_response, prev_response]
        bot_module.send_personal_standup_reminder()
        self.mock_app.client.chat_postMessage.assert_not_called()

    def test_sends_dm_with_today_section(self):
        """TC-14-04: Sends DM with extracted Today section when available."""
        self._set_prev_report("Yesterday: fixed bug X\nToday: ship feature Y, 1 day left\nBlockers: none")
        bot_module.send_personal_standup_reminder()
        self.mock_app.client.chat_postMessage.assert_called_once()
        call_kwargs = self.mock_app.client.chat_postMessage.call_args[1]
        self.assertEqual(call_kwargs['channel'], 'U0821BRMJ4R')
        self.assertTrue(call_kwargs['text'].startswith(
            "Quick nudge: your standup update is still missing. Please reply in today's active thread before 13:00.\n\n"
        ))
        self.assertIn("*Yesterday's plan for Today:*", call_kwargs['text'])
        self.assertIn('ship feature Y', call_kwargs['text'])

    def test_sends_dm_with_full_post_when_no_today_section(self):
        """TC-14-05: Falls back to full post when Today section can't be parsed."""
        self._set_prev_report("Some unstructured update without today section")
        bot_module.send_personal_standup_reminder()
        self.mock_app.client.chat_postMessage.assert_called_once()
        call_kwargs = self.mock_app.client.chat_postMessage.call_args[1]
        self.assertIn(
            "Quick nudge: your standup update is still missing. I couldn't isolate yesterday's Today section, so here's the full previous post.",
            call_kwargs['text'],
        )
        self.assertIn('unstructured update', call_kwargs['text'])

    def test_dm_includes_thread_link_when_available(self):
        """TC-14-06: DM includes link to today's standup thread."""
        self._set_prev_report("Yesterday: X\nToday: Y\nBlockers: none")
        bot_module.send_personal_standup_reminder()
        call_kwargs = self.mock_app.client.chat_postMessage.call_args[1]
        self.assertIn('slack.com/archives', call_kwargs['text'])


class TestExtractTodaySection(unittest.TestCase):

    def test_extracts_today_section(self):
        text = "Yesterday: fixed X\nToday: deploy feature Y\nBlockers: none"
        result = bot_module._extract_today_section(text)
        self.assertEqual(result, "deploy feature Y")

    def test_extracts_bold_format(self):
        text = "*Yesterday:* fixed X\n*Today (by EOD):* ship Z, 1 day\n*Blockers:* none"
        result = bot_module._extract_today_section(text)
        self.assertIn("ship Z", result)

    def test_returns_empty_when_no_today(self):
        result = bot_module._extract_today_section("Random text with no sections")
        self.assertEqual(result, "")


# ---------------------------------------------------------
# Entry point
# ---------------------------------------------------------
if __name__ == '__main__':
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    suite.addTests(loader.loadTestsFromTestCase(TestConfiguration))
    suite.addTests(loader.loadTestsFromTestCase(TestSupabaseClient))
    suite.addTests(loader.loadTestsFromTestCase(TestPostDailyThread))
    suite.addTests(loader.loadTestsFromTestCase(TestCheckMissingReports))
    suite.addTests(loader.loadTestsFromTestCase(TestGetMissingUsersToday))
    suite.addTests(loader.loadTestsFromTestCase(TestHandleMessageEvents))
    suite.addTests(loader.loadTestsFromTestCase(TestPhrases))
    suite.addTests(loader.loadTestsFromTestCase(TestPostDailyThreadExtended))
    suite.addTests(loader.loadTestsFromTestCase(TestCheckMissingReportsExtended))
    suite.addTests(loader.loadTestsFromTestCase(TestEndOfDayEscalation))
    suite.addTests(loader.loadTestsFromTestCase(TestHandleMessageEdgeCases))
    suite.addTests(loader.loadTestsFromTestCase(TestMainFunction))
    suite.addTests(loader.loadTestsFromTestCase(TestGetVacationUsers))
    suite.addTests(loader.loadTestsFromTestCase(TestSendDeployNotification))
    suite.addTests(loader.loadTestsFromTestCase(TestThreadBoostsRemoved))
    suite.addTests(loader.loadTestsFromTestCase(TestPersonalStandupReminder))
    suite.addTests(loader.loadTestsFromTestCase(TestExtractTodaySection))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
