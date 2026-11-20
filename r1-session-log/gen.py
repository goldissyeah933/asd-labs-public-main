#!/usr/bin/env python3
"""Генератор входов для замеров Р1. Два интерфейса.

1) Прежний (его использует проверяющий скрипт):

       python3 gen.py <n> [seed]

   Печатает в stdout журнал из n событий: корректно вложенные пары
   LOGIN/LOGOUT, остаток стека закрывается в конце; время обработки линейно
   по n.

2) Расширенный (для замеров на растущих размерах и отладки):

       python3 gen.py <size> <type> [output] [--seed N]

   Типы:
     balanced       — ровно size событий корректного вложенного журнала
                      (при нечётном size последнее событие — незакрытый LOGIN);
     only_login     — size подряд идущих LOGIN, стек растёт до size;
     random_garbage — size случайных строк: мусор вперемешку с событиями.

   Если output не указан, журнал печатается в stdout. Seed по умолчанию 1.
"""
import random
import sys

TYPES = ("balanced", "only_login", "random_garbage")
BATCH = 1 << 14

USAGE = ("usage: gen.py <n> [seed]\n"
         "       gen.py <size> <type> [output] [--seed N]\n"
         "types: " + ", ".join(TYPES))


def parse_int(text, what):
    try:
        return int(text)
    except ValueError:
        sys.exit(f"gen.py: {what} must be an integer, got {text!r}")


def parse_args(argv):
    """Разбирает аргументы; возвращает (mode, size, seed, out_path)."""
    args = argv[1:]
    seed = None
    positional = []
    i = 0
    while i < len(args):
        if args[i] == "--seed":
            if i + 1 >= len(args):
                sys.exit(USAGE)
            seed = parse_int(args[i + 1], "--seed")
            i += 2
        else:
            positional.append(args[i])
            i += 1

    if not positional:
        sys.exit(USAGE)
    size = parse_int(positional[0], "<size>")
    if size < 0:
        sys.exit("gen.py: <size> must be non-negative")
    if seed is None:
        seed = 1

    if len(positional) == 1:  # прежний интерфейс: gen.py <n>
        return ("legacy", size, seed, None)

    kind = positional[1]
    if kind in TYPES:  # расширенный интерфейс
        if len(positional) > 3:
            sys.exit(USAGE)
        out_path = positional[2] if len(positional) == 3 else None
        return (kind, size, seed, out_path)

    # прежний интерфейс с позиционным seed: gen.py <n> <seed>
    if len(positional) == 2:
        return ("legacy", size, parse_int(positional[1], "seed"), None)

    sys.exit(USAGE)


def gen_legacy(n, seed):
    """Прежний генератор: n событий + закрытие остатка (алгоритм не менялся)."""
    rng = random.Random(seed)
    out = []
    stack = []
    events = n
    for _ in range(events):
        # открываем новую сессию либо закрываем последнюю, сохраняя вложенность
        if stack and (len(stack) > 30 or rng.random() < 0.5):
            name = stack.pop()
            out.append(f"LOGOUT {name}")
        else:
            name = f"u{rng.randrange(1_000_000)}"
            stack.append(name)
            out.append(f"LOGIN {name}")
    while stack:
        out.append(f"LOGOUT {stack.pop()}")
    return out


def gen_balanced(size, rng):
    """Ровно size событий корректного вложенного журнала.

    Пушим, только если оставшихся событий хватит, чтобы всё закрыть; при
    нечётном size последний LOGIN остаётся незакрытым.
    """
    depth = 0
    top = 0
    for left in range(size, 0, -1):
        can_push = depth + 1 <= left - 1
        if depth == 0:
            push = True
        elif not can_push:
            push = False
        else:
            push = rng.random() < 0.5
        if push:
            top += 1
            depth += 1
            yield f"LOGIN u{top}"
        else:
            yield f"LOGOUT u{top}"
            top -= 1
            depth -= 1


def gen_only_login(size):
    for i in range(1, size + 1):
        yield f"LOGIN u{i}"


def gen_random_garbage(size, rng):
    """Мусорные строки вперемешку с валидными и невалидными событиями."""
    junk = ["", "   ", "LOGIN", "LOGOUT", "LOGIN alice bob", "login alice",
            "LOGOUT alice extra", "LOGIN a-b", "LOGIN a_b", "HELLO world",
            "123 456", "!!! ???"]
    names = [f"u{i}" for i in range(1000)]
    for _ in range(size):
        r = rng.random()
        if r < 0.30:
            yield rng.choice(junk)
        elif r < 0.65:
            yield "LOGIN " + rng.choice(names)
        else:
            yield "LOGOUT " + rng.choice(names)


def write_lines(stream, lines):
    """Пишет строки пачками: память ограничена, системных вызовов немного."""
    buf = []
    for line in lines:
        buf.append(line)
        if len(buf) >= BATCH:
            stream.write(("\n".join(buf) + "\n").encode("utf-8"))
            buf.clear()
    if buf:
        stream.write(("\n".join(buf) + "\n").encode("utf-8"))


def main():
    mode, size, seed, out_path = parse_args(sys.argv)
    if mode == "legacy":
        lines = gen_legacy(size, seed)
    elif mode == "balanced":
        lines = gen_balanced(size, random.Random(seed))
    elif mode == "only_login":
        lines = gen_only_login(size)
    else:
        lines = gen_random_garbage(size, random.Random(seed))

    if mode == "legacy" or out_path is None:
        write_lines(sys.stdout.buffer, lines)
    else:
        with open(out_path, "wb") as fout:
            write_lines(fout, lines)
    return 0


if __name__ == "__main__":
    sys.exit(main())
