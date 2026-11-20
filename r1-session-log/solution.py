#!/usr/bin/env python3
"""Анализ журнала сессий средствами стека (базовый уровень Р1).

Запуск:
    python3 solution.py <вход.txt> <выход.txt> [--bench]

Стек реализован самостоятельно (динамический массив с ручным удвоением
ёмкости); list/deque/LifoQueue как готовый стек не используются, рекурсии нет.
"""

import sys
import time

# Строка длиннее этого лимита (в байтах, без учёта перевода строки) считается
# bad_event; её остаток дочитывается и выбрасывается, не накапливаясь в памяти.
MAX_LINE_BYTES = 1 << 20  # 1 МиБ

_UTF8_BOM = b"\xef\xbb\xbf"
_DISCARD_CHUNK = 1 << 16  # шаг чтения при выбрасывании остатка длинной строки

EXIT_OK = 0
EXIT_IO = 1
EXIT_USAGE = 2
EXIT_MEMORY = 3

USAGE = "usage: python3 solution.py <input> <output> [--bench]"


class Stack:
    """Стек (LIFO) на собственном динамическом массиве."""

    __slots__ = ("_data", "_size")

    def __init__(self, capacity=8):
        self._data = [None] * capacity
        self._size = 0

    def is_empty(self):
        return self._size == 0

    def size(self):
        return self._size

    def push(self, item):
        if self._size == len(self._data):
            # Удвоение ёмкости: push в среднем O(1).
            self._data.extend([None] * max(1, len(self._data)))
        self._data[self._size] = item
        self._size += 1

    def pop(self):
        if self._size == 0:
            raise IndexError("pop from empty stack")
        self._size -= 1
        item = self._data[self._size]
        self._data[self._size] = None  # не держим ссылку на снятый элемент
        return item

    def top(self):
        if self._size == 0:
            raise IndexError("top of empty stack")
        return self._data[self._size - 1]


class LineWriter:
    """Буферизованный вывод: одна запись на пачку строк, а не на строку."""

    __slots__ = ("_file", "_buf")
    _BATCH = 8192

    def __init__(self, file):
        self._file = file
        self._buf = []

    def line(self, text):
        self._buf.append(text)
        if len(self._buf) >= self._BATCH:
            self.flush()

    def flush(self):
        if self._buf:
            self._file.write("\n".join(self._buf))
            self._file.write("\n")
            self._buf.clear()


def iter_raw_lines(fin, limit=MAX_LINE_BYTES):
    """Построчно читает бинарный файл, не загружая его в память.

    Отдаёт bytes — сырую строку, либо None, если строка длиннее limit байт
    (остаток такой строки дочитывается и выбрасывается).
    """
    while True:
        chunk = fin.readline(limit + 1)
        if not chunk:  # конец файла
            return
        if chunk.endswith(b"\n") or len(chunk) <= limit:
            yield chunk  # строка целиком уложилась в лимит
        else:
            _discard_line(fin)  # слишком длинная: выбрасываем остаток
            yield None


def _discard_line(fin):
    """Дочитывает и выбрасывает остаток слишком длинной строки."""
    while True:
        chunk = fin.readline(_DISCARD_CHUNK)
        if not chunk or chunk.endswith(b"\n"):
            return


def process(raw_lines, writer):
    """Один проход по строкам; возвращает число завершённых сессий."""
    stack = Stack()
    completed = 0
    first_line = True

    for line_no, raw in enumerate(raw_lines, 1):
        if first_line:
            first_line = False
            if raw is not None and raw.startswith(_UTF8_BOM):
                raw = raw[len(_UTF8_BOM):]  # BOM в начале файла — не ошибка

        if raw is None:  # строка превысила лимит
            writer.line(f"ERROR {line_no} bad_event")
            continue

        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            writer.line(f"ERROR {line_no} bad_event")
            continue

        parts = text.split()
        if not parts:
            continue  # пустая строка: номер учитывается, событие — нет
        if len(parts) != 2:
            writer.line(f"ERROR {line_no} bad_event")
            continue

        command, name = parts
        if not name.isalnum() or (command != "LOGIN" and command != "LOGOUT"):
            writer.line(f"ERROR {line_no} bad_event")
            continue

        if command == "LOGIN":
            stack.push((name, line_no))
        elif stack.is_empty():
            writer.line(f"ERROR {line_no} logout_without_login")
        elif stack.top()[0] == name:
            stack.pop()
            completed += 1
        else:
            writer.line(f"ERROR {line_no} order_violation")

    # Незакрытые сессии — от дна стека (раньше открыта) к вершине:
    # перекладываем в обратный стек, чтобы выдать по возрастанию номера строки.
    reversed_stack = Stack()
    while not stack.is_empty():
        reversed_stack.push(stack.pop())
    while not reversed_stack.is_empty():
        _name, open_line = reversed_stack.pop()
        writer.line(f"ERROR {open_line} session_not_closed")

    return completed


def main(argv):
    args = [a for a in argv[1:] if a != "--bench"]
    bench = (len(argv) - 1) - len(args) > 0
    if len(args) != 2:
        sys.stderr.write(USAGE + "\n")
        return EXIT_USAGE
    in_path, out_path = args

    try:
        with open(in_path, "rb") as fin, \
                open(out_path, "w", encoding="utf-8", newline="\n") as fout:
            writer = LineWriter(fout)
            if bench:
                # Режим замера: сначала чтение всего файла, затем разбор.
                t0 = time.perf_counter()
                raw_lines = list(iter_raw_lines(fin))
                t1 = time.perf_counter()
                completed = process(raw_lines, writer)
                t2 = time.perf_counter()
                sys.stderr.write("read_time %.6f\n" % (t1 - t0))
                sys.stderr.write("parse_time %.6f\n" % (t2 - t1))
            else:
                completed = process(iter_raw_lines(fin), writer)
            writer.line(f"SESSIONS {completed}")
            writer.flush()
    except OSError as exc:
        sys.stderr.write("I/O error: %s\n" % exc)
        return EXIT_IO
    except MemoryError:
        sys.stderr.write("out of memory\n")
        return EXIT_MEMORY
    except Exception as exc:  # страховка: никаких трассировок наружу
        sys.stderr.write("error: %s\n" % exc)
        return EXIT_IO
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main(sys.argv))
