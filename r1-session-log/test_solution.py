#!/usr/bin/env python3
"""Тесты для solution.py (unittest; запускаются и через pytest).

    python3 -m unittest test_solution -v
"""

import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SOLUTION = os.path.join(HERE, "solution.py")
PUBLIC_TESTS = os.path.join(HERE, "tests", "public")
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from solution import MAX_LINE_BYTES, Stack  # noqa: E402


def run_solution(data, extra_args=(), timeout=600):
    """Запускает solution.py на байтах data.

    Возвращает (код возврата, stdout, stderr, текст выходного файла или None).
    """
    with tempfile.TemporaryDirectory() as tmp:
        in_path = os.path.join(tmp, "input.txt")
        out_path = os.path.join(tmp, "output.txt")
        with open(in_path, "wb") as fh:
            fh.write(data)
        proc = subprocess.run(
            [sys.executable, SOLUTION, in_path, out_path] + list(extra_args),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout,
        )
        text = None
        if os.path.exists(out_path):
            with open(out_path, "r", encoding="utf-8") as fh:
                text = fh.read()
        return (proc.returncode,
                proc.stdout.decode("utf-8", "replace"),
                proc.stderr.decode("utf-8", "replace"),
                text)


class BaseCase(unittest.TestCase):
    maxDiff = None

    def assert_solution(self, data, expected, timeout=600):
        code, out, err, text = run_solution(data, timeout=timeout)
        self.assertEqual(code, 0, "ненулевой код возврата, stderr: %s" % err)
        self.assertEqual(out, "", "stdout должен оставаться пустым")
        self.assertEqual(text, expected)


class TestExamples(BaseCase):
    """Оба примера из условия — сравнение до токена."""

    def test_example_1(self):
        data = (b"LOGIN alice\n"
                b"LOGIN bob\n"
                b"LOGOUT bob\n"
                b"LOGOUT alice\n"
                b"LOGOUT carol\n")
        self.assert_solution(
            data, "ERROR 5 logout_without_login\nSESSIONS 2\n")

    def test_example_2(self):
        data = (b"LOGIN alice\n"
                b"LOGIN bob\n"
                b"LOGOUT alice\n"
                b"LOGOUT bob\n")
        self.assert_solution(
            data,
            "ERROR 3 order_violation\n"
            "ERROR 1 session_not_closed\n"
            "SESSIONS 1\n")


class TestFormatting(BaseCase):
    """Пустые строки, пробелы, CRLF, отсутствие завершающего \n."""

    def test_empty_file(self):
        self.assert_solution(b"", "SESSIONS 0\n")

    def test_only_blank_lines(self):
        self.assert_solution(b"\n   \n\t\n", "SESSIONS 0\n")

    def test_line_numbers_with_blank_lines(self):
        data = (b"\n"                # 1: пустая
                b"LOGIN alice\n"     # 2
                b"   \n"             # 3: пустая
                b"LOGOUT alice\n"    # 4
                b"\n"                # 5: пустая
                b"LOGOUT bob\n")     # 6
        self.assert_solution(
            data, "ERROR 6 logout_without_login\nSESSIONS 1\n")

    def test_extra_spaces_and_tabs(self):
        data = b" \t LOGIN\t\talice  \n\t LOGOUT   alice \t\n"
        self.assert_solution(data, "SESSIONS 1\n")

    def test_crlf(self):
        data = b"LOGIN alice\r\nLOGOUT alice\r\nLOGIN bob\r\n"
        self.assert_solution(
            data, "ERROR 3 session_not_closed\nSESSIONS 1\n")

    def test_no_trailing_newline(self):
        data = b"LOGIN alice\nLOGOUT alice"
        self.assert_solution(data, "SESSIONS 1\n")


class TestLogic(BaseCase):
    """Ошибки модели: выход без входа, порядок, незакрытые сессии."""

    def test_logout_without_login(self):
        data = b"LOGOUT x\nLOGIN x\nLOGOUT x\nLOGOUT x\n"
        self.assert_solution(
            data,
            "ERROR 1 logout_without_login\n"
            "ERROR 4 logout_without_login\n"
            "SESSIONS 1\n")

    def test_order_violation_keeps_stack(self):
        data = (b"LOGIN a\n"      # 1
                b"LOGIN b\n"      # 2
                b"LOGOUT a\n"     # 3: нарушение, b остаётся на вершине
                b"LOGOUT a\n"     # 4: нарушение ещё раз
                b"LOGOUT b\n")    # 5: штатно закрывает b
        self.assert_solution(
            data,
            "ERROR 3 order_violation\n"
            "ERROR 4 order_violation\n"
            "ERROR 1 session_not_closed\n"
            "SESSIONS 1\n")

    def test_several_unclosed_sorted_by_line(self):
        data = b"LOGIN c\nLOGIN a\nLOGIN b\n"
        self.assert_solution(
            data,
            "ERROR 1 session_not_closed\n"
            "ERROR 2 session_not_closed\n"
            "ERROR 3 session_not_closed\n"
            "SESSIONS 0\n")


class TestBadEvents(BaseCase):
    """Некорректные события: имена, регистр команд, число токенов."""

    def test_bad_names(self):
        data = (b"LOGIN a-b\n"    # 1: дефис
                b"LOGIN a_b\n"    # 2: подчёркивание
                b"LOGIN\n"        # 3: имя отсутствует
                b"LOGIN 123\n")   # 4: корректное событие
        self.assert_solution(
            data,
            "ERROR 1 bad_event\n"
            "ERROR 2 bad_event\n"
            "ERROR 3 bad_event\n"
            "ERROR 4 session_not_closed\n"
            "SESSIONS 0\n")

    def test_lowercase_command(self):
        data = b"login alice\nLogout alice\n"
        self.assert_solution(
            data, "ERROR 1 bad_event\nERROR 2 bad_event\nSESSIONS 0\n")

    def test_three_tokens(self):
        data = b"LOGIN alice extra\nLOGIN alice\nLOGOUT alice\n"
        self.assert_solution(data, "ERROR 1 bad_event\nSESSIONS 1\n")

    def test_unknown_command(self):
        data = b"HELLO alice\n"
        self.assert_solution(data, "ERROR 1 bad_event\nSESSIONS 0\n")


class TestEncodingAndLimits(BaseCase):
    """Кодировка, BOM, бинарный мусор, лимит длины строки."""

    def test_invalid_utf8(self):
        data = b"LOGIN \xff\xfe\nLOGIN alice\nLOGOUT alice\n"
        self.assert_solution(data, "ERROR 1 bad_event\nSESSIONS 1\n")

    def test_truncated_multibyte_char(self):
        data = b"LOGIN al\xd0"  # обрыв внутри двухбайтового символа
        self.assert_solution(data, "ERROR 1 bad_event\nSESSIONS 0\n")

    def test_nul_bytes(self):
        data = b"LOGIN al\x00ice\nLOGIN ok\nLOGOUT ok\n"
        self.assert_solution(data, "ERROR 1 bad_event\nSESSIONS 1\n")

    def test_binary_garbage(self):
        garbage = bytes(b for b in range(1, 256) if b != 0x0A) * 3
        data = garbage + b"\nLOGIN ok\nLOGOUT ok\n"
        self.assert_solution(data, "ERROR 1 bad_event\nSESSIONS 1\n")

    def test_bom_is_stripped(self):
        data = b"\xef\xbb\xbfLOGIN alice\nLOGOUT alice\n"
        self.assert_solution(data, "SESSIONS 1\n")

    def test_bom_alone_on_first_line(self):
        data = b"\xef\xbb\xbf\nLOGIN alice\nLOGOUT alice\n"
        self.assert_solution(data, "SESSIONS 1\n")

    def test_bom_in_the_middle_is_not_special(self):
        data = b"LOGIN alice\n\xef\xbb\xbfLOGOUT alice\n"
        self.assert_solution(
            data,
            "ERROR 2 bad_event\nERROR 1 session_not_closed\nSESSIONS 0\n")

    def test_line_longer_than_limit(self):
        long_line = b"LOGIN " + b"a" * (MAX_LINE_BYTES + 100) + b"\n"
        data = long_line + b"LOGIN alice\nLOGOUT alice\n"
        self.assert_solution(data, "ERROR 1 bad_event\nSESSIONS 1\n")

    def test_long_line_at_eof(self):
        data = b"LOGIN " + b"a" * (MAX_LINE_BYTES + 100)
        self.assert_solution(data, "ERROR 1 bad_event\nSESSIONS 0\n")

    def test_line_exactly_at_limit(self):
        name = b"a" * (MAX_LINE_BYTES - 6)  # "LOGIN " + name == лимит
        data = b"LOGIN " + name + b"\n"
        self.assert_solution(data, "ERROR 1 session_not_closed\nSESSIONS 0\n")


class TestStackUnit(unittest.TestCase):
    """Прямая проверка собственного класса Stack."""

    def test_operations(self):
        s = Stack()
        self.assertTrue(s.is_empty())
        self.assertEqual(s.size(), 0)
        with self.assertRaises(IndexError):
            s.pop()
        with self.assertRaises(IndexError):
            s.top()
        s.push(("a", 1))
        s.push(("b", 2))
        self.assertEqual(s.size(), 2)
        self.assertEqual(s.top(), ("b", 2))
        self.assertEqual(s.pop(), ("b", 2))
        self.assertEqual(s.pop(), ("a", 1))
        self.assertTrue(s.is_empty())

    def test_growth_and_drain(self):
        s = Stack()
        for i in range(50000):  # несколько удвоений ёмкости
            s.push((str(i), i))
        self.assertEqual(s.size(), 50000)
        for i in range(49999, -1, -1):
            self.assertEqual(s.pop(), (str(i), i))
        self.assertTrue(s.is_empty())


class TestBenchMode(BaseCase):
    """Режим --bench: тот же вывод плюс два числа в stderr."""

    def test_bench_matches_normal_output(self):
        data = b"LOGIN alice\nLOGOUT bob\nLOGOUT alice\nLOGIN bob\n"
        expected = ("ERROR 2 order_violation\n"
                    "ERROR 4 session_not_closed\n"
                    "SESSIONS 1\n")
        code, out, err, text = run_solution(data, extra_args=("--bench",))
        self.assertEqual(code, 0, err)
        self.assertEqual(out, "")
        self.assertEqual(text, expected)
        self.assertIn("read_time", err)
        self.assertIn("parse_time", err)


class TestCliRobustness(unittest.TestCase):
    """Ошибки запуска: сообщение в stderr, ненулевой код, без трассировки."""

    def test_missing_input_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc = subprocess.run(
                [sys.executable, SOLUTION,
                 os.path.join(tmp, "no_such_file.txt"),
                 os.path.join(tmp, "out.txt")],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
        self.assertNotEqual(proc.returncode, 0)
        self.assertNotIn(b"Traceback", proc.stderr)
        self.assertTrue(proc.stderr.strip())

    def test_wrong_argument_count(self):
        proc = subprocess.run(
            [sys.executable, SOLUTION],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
        self.assertNotEqual(proc.returncode, 0)
        self.assertNotIn(b"Traceback", proc.stderr)
        self.assertTrue(proc.stderr.strip())

    def test_unknown_flag_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            in_path = os.path.join(tmp, "in.txt")
            with open(in_path, "wb") as fh:
                fh.write(b"")
            proc = subprocess.run(
                [sys.executable, SOLUTION, in_path,
                 os.path.join(tmp, "out.txt"), "--oops"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
        self.assertNotEqual(proc.returncode, 0)
        self.assertNotIn(b"Traceback", proc.stderr)


class TestScale(unittest.TestCase):
    """Большие входы: без падений, рекурсии нет, ошибки посчитаны верно."""

    def test_million_logins(self):
        n = 1000000
        data = b"LOGIN u\n" * n
        code, out, err, text = run_solution(data)
        self.assertEqual(code, 0, err)
        self.assertEqual(text.count("session_not_closed"), n)
        self.assertEqual(text.count("\n"), n + 1)  # n ошибок + SESSIONS
        self.assertTrue(text.startswith("ERROR 1 session_not_closed\n"))
        self.assertTrue(
            text.endswith("ERROR %d session_not_closed\nSESSIONS 0\n" % n))

    def test_million_lines_balanced(self):
        pairs = 500000
        data = b"LOGIN u\nLOGOUT u\n" * pairs
        code, out, err, text = run_solution(data)
        self.assertEqual(code, 0, err)
        self.assertEqual(text, "SESSIONS %d\n" % pairs)


class TestRepositoryPublicTests(unittest.TestCase):
    """Публичные тесты репозитория (tests/public), если папка рядом."""

    @unittest.skipUnless(os.path.isdir(PUBLIC_TESTS), "нет папки tests/public")
    def test_public_cases_match_by_tokens(self):
        names = sorted(n for n in os.listdir(PUBLIC_TESTS)
                       if n.endswith(".in"))
        self.assertTrue(names, "не найдено ни одного .in")
        for name in names:
            with self.subTest(case=name):
                with open(os.path.join(PUBLIC_TESTS, name), "rb") as fh:
                    data = fh.read()
                with open(os.path.join(PUBLIC_TESTS, name[:-3] + ".out"),
                          "r", encoding="utf-8") as fh:
                    expected_tokens = fh.read().split()
                code, _out, err, text = run_solution(data)
                self.assertEqual(code, 0, err)
                self.assertEqual(text.split(), expected_tokens)


if __name__ == "__main__":
    unittest.main()
