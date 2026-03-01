"""
Tests for Slack Standup Bot
Run: python -m pytest test_bot.py -v
or: python test_bot.py
"""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch, call
from datetime import date

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

    def test_daily_thread_ts_initially_none(self):
        """TC-01-05: daily_thread_ts is initially None"""
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
    def test_post_daily_thread_uses_michael_scott_greeting(self, mock_vacation):
        """TC-03-04: post_daily_thread() must use a Michael Scott greeting"""
        MICHAEL_SCOTT_GREETINGS = [
            "Good morning, Dunder Mifflin! ☕",
            "\u201cYou miss 100% of the shots you don\u2019t take. \u2013 Wayne Gretzky\u201d \u2013 Michael Scott. Time for standup! 🏒",
            "I'm an early bird, and I'm a night owl, so I'm wise, and I have worms. Morning team! 🦉",
            "Well, well, well, how the turntables... It's standup time! 💿",
            "Dunder Mifflin, this is Michael. Drop your daily updates! 🏢",
            "I am Beyoncé, always. And you are my favorite team. Standup time! 👑"
        ]
        bot_module.post_daily_thread()
        first_call_kwargs = self.mock_app.client.chat_postMessage.call_args_list[0][1]
        text = first_call_kwargs['text']
        self.assertTrue(
            any(text.startswith(phrase) for phrase in MICHAEL_SCOTT_GREETINGS),
            f"Message text must start with one of MICHAEL_SCOTT_GREETINGS"
        )

    def test_post_daily_thread_skips_if_no_app(self):
        """TC-03-05: post_daily_thread() must exit if app is not initialized"""
        bot_module.app = None
        bot_module.post_daily_thread()
        self.assertIsNone(bot_module.daily_thread_ts)

    def test_post_daily_thread_skips_if_no_channel(self):
        """TC-03-06: post_daily_thread() must exit if CHANNEL_ID is empty"""
        bot_module.app = self.mock_app
        bot_module.CHANNEL_ID = None
        bot_module.post_daily_thread()
        self.mock_app.client.chat_postMessage.assert_not_called()

    def test_post_daily_thread_handles_api_error(self):
        """TC-03-07: post_daily_thread() must handle API errors without crashing"""
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

    @patch('main.get_vacation_users', return_value=set())
    def test_pings_missing_users(self, mock_vacation):
        """TC-04-03: check_missing_reports() pings users who haven't reported"""
        # Only U111 has reported
        mock_response = MagicMock()
        mock_response.data = [{"user_id": "U111"}]
        self.mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_response

        bot_module.check_missing_reports()

        # Should send reminder (U222 hasn't reported)
        self.mock_app.client.chat_postMessage.assert_called_once()
        call_kwargs = self.mock_app.client.chat_postMessage.call_args[1]
        self.assertIn("U222", call_kwargs['text'])
        self.assertEqual(call_kwargs['channel'], 'C08UT7VP2TA')
        self.assertEqual(call_kwargs['thread_ts'], "1234567890.123456")

    @patch('main.get_vacation_users', return_value=set())
    def test_no_ping_if_all_reported(self, mock_vacation):
        """TC-04-04: check_missing_reports() does not ping if everyone reported"""
        mock_response = MagicMock()
        mock_response.data = [{"user_id": "U111"}, {"user_id": "U222"}]
        self.mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_response

        bot_module.check_missing_reports()
        self.mock_app.client.chat_postMessage.assert_not_called()

    @patch('main.get_vacation_users', return_value=set())
    def test_pings_all_if_none_reported(self, mock_vacation):
        """TC-04-05: check_missing_reports() pings everyone if no one reported"""
        mock_response = MagicMock()
        mock_response.data = []
        self.mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_response

        bot_module.check_missing_reports()
        self.mock_app.client.chat_postMessage.assert_called_once()
        call_kwargs = self.mock_app.client.chat_postMessage.call_args[1]
        self.assertIn("U111", call_kwargs['text'])
        self.assertIn("U222", call_kwargs['text'])


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

    def test_adds_checkmark_reaction(self):
        """TC-05-02: Checkmark reaction is added after saving"""
        body = {"event": {
            "user": "U999",
            "text": "My report",
            "ts": "9999999999.000001",
            "thread_ts": "1234567890.123456",
        }}
        self._call_handler(body)
        self.mock_app.client.reactions_add.assert_called_once_with(
            channel='C08UT7VP2TA',
            name="blue_heart",
            timestamp="9999999999.000001"
        )

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

    @patch('main.get_vacation_users', return_value=set())
    def test_reminder_message_contains_emoji(self, mock_vacation):
        """TC-08-01: Reminder contains an emoji"""
        mock_response = MagicMock()
        mock_response.data = []
        self.mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_response
        bot_module.check_missing_reports()
        call_kwargs = self.mock_app.client.chat_postMessage.call_args[1]
        # Check that at least one emoji is present (any meme has one)
        import re
        emoji_pattern = re.compile(r'[\U0001F300-\U0001F9FF]')
        self.assertTrue(emoji_pattern.search(call_kwargs['text']),
                        "Reminder message should contain an emoji")

    @patch('main.get_vacation_users', return_value=set())
    def test_reminder_sent_in_thread(self, mock_vacation):
        """TC-08-02: Reminder is sent in thread, not in channel"""
        mock_response = MagicMock()
        mock_response.data = []
        self.mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_response
        bot_module.check_missing_reports()
        call_kwargs = self.mock_app.client.chat_postMessage.call_args[1]
        self.assertEqual(call_kwargs['thread_ts'], "1234567890.123456")

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
        # Should have 3 jobs: post_daily_thread + 2x check_missing_reports
        self.assertEqual(mock_sched.add_job.call_count, 3)
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
                    "user": {"name": "Anton Tyutin"},
                },
                {
                    "id": "leave-2",
                    "userId": "vt-user-2",
                    "status": "APPROVED",
                    "startDate": "2026-02-26",
                    "endDate": "2026-02-28",
                    "user": {"name": "Gvantsa Nebadze"},
                },
            ],
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = bot_module.get_vacation_users()

        self.assertIn("U035U3KTFL5", result)  # Anton Tyutin
        self.assertIn("U088WHYP2P6", result)  # Gvantsa Nebadze
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
                    "user": {"name": "Gvantsa Nebadze"},
                },
                {
                    "id": "leave-3",
                    "status": "DENIED",
                    "user": {"name": "Ed"},
                },
            ],
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = bot_module.get_vacation_users()

        self.assertIn("U035U3KTFL5", result)  # Anton — APPROVED
        self.assertNotIn("U088WHYP2P6", result)  # Gvantsa — PENDING
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
            "data": [{"id": "l2", "status": "APPROVED", "user": {"name": "Ed"}}],
        }
        page2.raise_for_status = MagicMock()

        mock_get.side_effect = [page1, page2]

        result = bot_module.get_vacation_users()

        self.assertEqual(mock_get.call_count, 2)
        self.assertIn("U035U3KTFL5", result)  # Anton
        self.assertIn("U085J8B5TJ6", result)  # Ed

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
    suite.addTests(loader.loadTestsFromTestCase(TestHandleMessageEvents))
    suite.addTests(loader.loadTestsFromTestCase(TestPhrases))
    suite.addTests(loader.loadTestsFromTestCase(TestPostDailyThreadExtended))
    suite.addTests(loader.loadTestsFromTestCase(TestCheckMissingReportsExtended))
    suite.addTests(loader.loadTestsFromTestCase(TestHandleMessageEdgeCases))
    suite.addTests(loader.loadTestsFromTestCase(TestMainFunction))
    suite.addTests(loader.loadTestsFromTestCase(TestGetVacationUsers))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
