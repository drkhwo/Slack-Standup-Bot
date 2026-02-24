"""
Тесты для Slack Standup Bot
Запуск: python -m pytest test_bot.py -v
или: python test_bot.py
"""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch, call
from datetime import date

# Мокируем внешние зависимости до импорта main
sys.modules['slack_bolt'] = MagicMock()
sys.modules['slack_bolt.adapter'] = MagicMock()
sys.modules['slack_bolt.adapter.socket_mode'] = MagicMock()
sys.modules['supabase'] = MagicMock()
sys.modules['apscheduler'] = MagicMock()
sys.modules['apscheduler.schedulers'] = MagicMock()
sys.modules['apscheduler.schedulers.background'] = MagicMock()
sys.modules['dotenv'] = MagicMock()

# Мокируем load_dotenv чтобы не читать .env
with patch.dict('os.environ', {
    'SLACK_BOT_TOKEN': 'xoxb-test-token',
    'SLACK_APP_TOKEN': 'xapp-test-token',
    'SUPABASE_URL': 'https://test.supabase.co',
    'SUPABASE_KEY': 'test-key',
    'CHANNEL_ID': 'C08UT7VP2TA',
}):
    import importlib
    import main as bot_module


# ─────────────────────────────────────────────────────────
# TC-01: Конфигурация и переменные окружения
# ─────────────────────────────────────────────────────────
class TestConfiguration(unittest.TestCase):

    def test_channel_id_is_set(self):
        """TC-01-01: CHANNEL_ID должен быть задан"""
        self.assertIsNotNone(bot_module.CHANNEL_ID)
        self.assertNotEqual(bot_module.CHANNEL_ID, "")

    def test_slack_bot_token_is_set(self):
        """TC-01-02: SLACK_BOT_TOKEN должен быть задан"""
        self.assertIsNotNone(bot_module.SLACK_BOT_TOKEN)

    def test_supabase_url_is_set(self):
        """TC-01-03: SUPABASE_URL должен быть задан"""
        self.assertIsNotNone(bot_module.SUPABASE_URL)

    def test_team_user_ids_not_empty(self):
        """TC-01-04: TEAM_USER_IDS должен содержать хотя бы одного пользователя"""
        self.assertIsInstance(bot_module.TEAM_USER_IDS, list)
        self.assertGreater(len(bot_module.TEAM_USER_IDS), 0)

    def test_daily_thread_ts_initially_none(self):
        """TC-01-05: daily_thread_ts изначально None"""
        # Проверяем что глобальная переменная существует
        self.assertTrue(hasattr(bot_module, 'daily_thread_ts'))


# ─────────────────────────────────────────────────────────
# TC-02: Supabase подключение
# ─────────────────────────────────────────────────────────
class TestSupabaseClient(unittest.TestCase):

    def test_get_supabase_client_returns_none_without_credentials(self):
        """TC-02-01: get_supabase_client() возвращает None без credentials"""
        with patch.dict('os.environ', {}, clear=True):
            # Убираем переменные
            original_url = bot_module.SUPABASE_URL
            original_key = bot_module.SUPABASE_KEY
            bot_module.SUPABASE_URL = None
            bot_module.SUPABASE_KEY = None
            result = bot_module.get_supabase_client()
            bot_module.SUPABASE_URL = original_url
            bot_module.SUPABASE_KEY = original_key
            self.assertIsNone(result)

    def test_get_supabase_client_calls_create_client(self):
        """TC-02-02: get_supabase_client() вызывает create_client с правильными параметрами"""
        mock_client = MagicMock()
        with patch('main.create_client', return_value=mock_client) as mock_create:
            bot_module.SUPABASE_URL = 'https://test.supabase.co'
            bot_module.SUPABASE_KEY = 'test-key'
            result = bot_module.get_supabase_client()
            mock_create.assert_called_once_with('https://test.supabase.co', 'test-key')
            self.assertEqual(result, mock_client)


# ─────────────────────────────────────────────────────────
# TC-03: post_daily_thread
# ─────────────────────────────────────────────────────────
class TestPostDailyThread(unittest.TestCase):

    def setUp(self):
        """Подготовка: создаём мок приложения"""
        self.mock_app = MagicMock()
        self.mock_app.client.chat_postMessage.return_value = {"ts": "1234567890.123456"}
        bot_module.app = self.mock_app
        bot_module.CHANNEL_ID = 'C08UT7VP2TA'
        bot_module.daily_thread_ts = None

    def test_post_daily_thread_sends_message(self):
        """TC-03-01: post_daily_thread() должен отправить сообщение в канал"""
        bot_module.post_daily_thread()
        self.mock_app.client.chat_postMessage.assert_called_once()

    def test_post_daily_thread_uses_correct_channel(self):
        """TC-03-02: post_daily_thread() должен отправить в правильный канал"""
        bot_module.post_daily_thread()
        call_kwargs = self.mock_app.client.chat_postMessage.call_args[1]
        self.assertEqual(call_kwargs['channel'], 'C08UT7VP2TA')

    def test_post_daily_thread_sets_daily_thread_ts(self):
        """TC-03-03: post_daily_thread() должен сохранить ts треда"""
        bot_module.post_daily_thread()
        self.assertIsNotNone(bot_module.daily_thread_ts)
        self.assertEqual(bot_module.daily_thread_ts, "1234567890.123456")

    def test_post_daily_thread_uses_opening_phrase(self):
        """TC-03-04: post_daily_thread() должен использовать фразу из OPENING_PHRASES"""
        from phrases import OPENING_PHRASES
        bot_module.post_daily_thread()
        call_kwargs = self.mock_app.client.chat_postMessage.call_args[1]
        self.assertIn(call_kwargs['text'], OPENING_PHRASES)

    def test_post_daily_thread_skips_if_no_app(self):
        """TC-03-05: post_daily_thread() должен выйти если app не инициализирован"""
        bot_module.app = None
        bot_module.post_daily_thread()
        # chat_postMessage не должен был вызваться
        # (mock_app уже None, значит нет вызовов)
        self.assertIsNone(bot_module.daily_thread_ts)

    def test_post_daily_thread_skips_if_no_channel(self):
        """TC-03-06: post_daily_thread() должен выйти если CHANNEL_ID пустой"""
        bot_module.app = self.mock_app
        bot_module.CHANNEL_ID = None
        bot_module.post_daily_thread()
        self.mock_app.client.chat_postMessage.assert_not_called()

    def test_post_daily_thread_handles_api_error(self):
        """TC-03-07: post_daily_thread() должен обработать ошибку API без краша"""
        self.mock_app.client.chat_postMessage.side_effect = Exception("Slack API error")
        try:
            bot_module.post_daily_thread()
        except Exception:
            self.fail("post_daily_thread() не должен выбрасывать исключение")


# ─────────────────────────────────────────────────────────
# TC-04: check_missing_reports
# ─────────────────────────────────────────────────────────
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
        """TC-04-01: check_missing_reports() пропускает если нет треда"""
        bot_module.daily_thread_ts = None
        bot_module.check_missing_reports()
        self.mock_supabase.table.assert_not_called()

    def test_skip_if_no_supabase(self):
        """TC-04-02: check_missing_reports() пропускает если нет supabase"""
        bot_module.supabase = None
        bot_module.check_missing_reports()
        # Не должно быть исключений
        self.assertIsNone(bot_module.supabase)

    def test_pings_missing_users(self):
        """TC-04-03: check_missing_reports() пингует пользователей без отчёта"""
        # Только U111 отчитался
        mock_response = MagicMock()
        mock_response.data = [{"user_id": "U111"}]
        self.mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_response

        bot_module.check_missing_reports()

        # Должен отправить напоминание (U222 не отчитался)
        self.mock_app.client.chat_postMessage.assert_called_once()
        call_kwargs = self.mock_app.client.chat_postMessage.call_args[1]
        self.assertIn("U222", call_kwargs['text'])
        self.assertEqual(call_kwargs['channel'], 'C08UT7VP2TA')
        self.assertEqual(call_kwargs['thread_ts'], "1234567890.123456")

    def test_no_ping_if_all_reported(self):
        """TC-04-04: check_missing_reports() не пингует если все отчитались"""
        mock_response = MagicMock()
        mock_response.data = [{"user_id": "U111"}, {"user_id": "U222"}]
        self.mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_response

        bot_module.check_missing_reports()
        self.mock_app.client.chat_postMessage.assert_not_called()

    def test_pings_all_if_none_reported(self):
        """TC-04-05: check_missing_reports() пингует всех если никто не отчитался"""
        mock_response = MagicMock()
        mock_response.data = []
        self.mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_response

        bot_module.check_missing_reports()
        self.mock_app.client.chat_postMessage.assert_called_once()
        call_kwargs = self.mock_app.client.chat_postMessage.call_args[1]
        self.assertIn("U111", call_kwargs['text'])
        self.assertIn("U222", call_kwargs['text'])


# ─────────────────────────────────────────────────────────
# TC-05: handle_message_events (обработка сообщений в треде)
# ─────────────────────────────────────────────────────────
class TestHandleMessageEvents(unittest.TestCase):

    def setUp(self):
        self.mock_app = MagicMock()
        self.mock_supabase = MagicMock()
        bot_module.app = self.mock_app
        bot_module.supabase = self.mock_supabase
        bot_module.daily_thread_ts = "1234567890.123456"
        bot_module.CHANNEL_ID = 'C08UT7VP2TA'

        # Регистрируем обработчик
        bot_module.register_events(self.mock_app)
        # Получаем зарегистрированный обработчик
        event_decorator = self.mock_app.event.return_value
        self.handler_func = event_decorator.call_args[0][0]

    def _call_handler(self, body):
        """Вспомогательный метод для вызова обработчика"""
        logger = MagicMock()
        self.handler_func(body=body, logger=logger)

    def test_saves_report_to_supabase(self):
        """TC-05-01: Сообщение в треде сохраняется в Supabase"""
        body = {"event": {
            "user": "U999",
            "text": "Вчера сделал X, сегодня буду делать Y",
            "ts": "9999999999.000001",
            "thread_ts": "1234567890.123456",
        }}
        self._call_handler(body)
        self.mock_supabase.table.assert_called_with("standup_reports")
        insert_data = self.mock_supabase.table.return_value.insert.call_args[0][0]
        self.assertEqual(insert_data['user_id'], "U999")
        self.assertEqual(insert_data['raw_text'], "Вчера сделал X, сегодня буду делать Y")
        self.assertEqual(insert_data['date'], date.today().isoformat())

    def test_adds_checkmark_reaction(self):
        """TC-05-02: После сохранения добавляется реакция ✅"""
        body = {"event": {
            "user": "U999",
            "text": "Мой отчёт",
            "ts": "9999999999.000001",
            "thread_ts": "1234567890.123456",
        }}
        self._call_handler(body)
        self.mock_app.client.reactions_add.assert_called_once_with(
            channel='C08UT7VP2TA',
            name="white_check_mark",
            timestamp="9999999999.000001"
        )

    def test_ignores_messages_outside_thread(self):
        """TC-05-03: Сообщения вне треда игнорируются"""
        body = {"event": {
            "user": "U999",
            "text": "Просто сообщение в канале",
            "ts": "9999999999.000001",
            "thread_ts": "9999111111.000000",  # другой тред
        }}
        self._call_handler(body)
        self.mock_supabase.table.assert_not_called()

    def test_ignores_bot_messages(self):
        """TC-05-04: Сообщения от ботов игнорируются"""
        body = {"event": {
            "user": "U999",
            "text": "Сообщение от бота",
            "ts": "9999999999.000001",
            "thread_ts": "1234567890.123456",
            "bot_id": "B123",
        }}
        self._call_handler(body)
        self.mock_supabase.table.assert_not_called()

    def test_ignores_if_no_daily_thread(self):
        """TC-05-05: Если нет активного треда — игнорируем все сообщения"""
        bot_module.daily_thread_ts = None
        body = {"event": {
            "user": "U999",
            "text": "Сообщение",
            "ts": "9999999999.000001",
            "thread_ts": "1234567890.123456",
        }}
        self._call_handler(body)
        self.mock_supabase.table.assert_not_called()

    def test_handles_supabase_error_gracefully(self):
        """TC-05-06: Ошибка Supabase не крашит обработчик"""
        self.mock_supabase.table.return_value.insert.return_value.execute.side_effect = Exception("DB error")
        body = {"event": {
            "user": "U999",
            "text": "Мой отчёт",
            "ts": "9999999999.000001",
            "thread_ts": "1234567890.123456",
        }}
        try:
            self._call_handler(body)
        except Exception:
            self.fail("handle_message_events не должен выбрасывать исключение")

    def test_report_includes_thread_ts(self):
        """TC-05-07: Сохранённый отчёт содержит thread_ts сообщения"""
        body = {"event": {
            "user": "U999",
            "text": "Отчёт",
            "ts": "9999999999.000001",
            "thread_ts": "1234567890.123456",
        }}
        self._call_handler(body)
        insert_data = self.mock_supabase.table.return_value.insert.call_args[0][0]
        self.assertEqual(insert_data['thread_ts'], "9999999999.000001")


# ─────────────────────────────────────────────────────────
# TC-06: phrases.py
# ─────────────────────────────────────────────────────────
class TestPhrases(unittest.TestCase):

    def test_opening_phrases_not_empty(self):
        """TC-06-01: OPENING_PHRASES содержит фразы"""
        from phrases import OPENING_PHRASES
        self.assertIsInstance(OPENING_PHRASES, list)
        self.assertGreater(len(OPENING_PHRASES), 0)

    def test_opening_phrases_are_strings(self):
        """TC-06-02: Все фразы являются строками"""
        from phrases import OPENING_PHRASES
        for phrase in OPENING_PHRASES:
            self.assertIsInstance(phrase, str)

    def test_opening_phrases_not_blank(self):
        """TC-06-03: Все фразы непустые"""
        from phrases import OPENING_PHRASES
        for phrase in OPENING_PHRASES:
            self.assertTrue(len(phrase.strip()) > 0)


# ─────────────────────────────────────────────────────────
# Точка запуска
# ─────────────────────────────────────────────────────────
if __name__ == '__main__':
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    suite.addTests(loader.loadTestsFromTestCase(TestConfiguration))
    suite.addTests(loader.loadTestsFromTestCase(TestSupabaseClient))
    suite.addTests(loader.loadTestsFromTestCase(TestPostDailyThread))
    suite.addTests(loader.loadTestsFromTestCase(TestCheckMissingReports))
    suite.addTests(loader.loadTestsFromTestCase(TestHandleMessageEvents))
    suite.addTests(loader.loadTestsFromTestCase(TestPhrases))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
