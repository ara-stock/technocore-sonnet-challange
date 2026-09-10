import sqlite3
import tempfile
import unittest
from pathlib import Path

from sonnet_validate import read_lexicon, validate_poem, validate_word, word_syllables

ROOT = Path(__file__).resolve().parents[1]
DID_A = "did:key:z6MkhaXgBZDvotDkL5257faiztiGiC2QtKLGpbnnEGta2doK"
DID_B = "did:key:z6MkereFQqHaUdcF7yVmHvY1rHpAvVjeCggaBVy45hmE8G6C"
LEXICON = {"the": 1, "i": 1, "deeded": 2, "i'd": 1, "wool": 1}


def poem_with(lines: int = 14, words: int = 10) -> str:
    return "\n".join([" ".join(["I"] * words)] * lines)


class WordTests(unittest.TestCase):
    def test_letter_reuse_case_prefix_and_punctuation(self):
        self.assertEqual(validate_word("THE;", DID_A, LEXICON), 1)
        # The shared did:key: prefix supplies d/e, and letter reuse is unlimited.
        self.assertEqual(validate_word("DeeDeD!", DID_B, LEXICON), 2)
        self.assertEqual(validate_word("I'd,", DID_B, LEXICON), 1)

    def test_missing_letters_and_invalid_dids_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "letters absent"):
            validate_word("wool", DID_A, LEXICON)
        for did in ("agent-a", DID_A + "#key", DID_A.upper(), None):
            with self.subTest(did=did), self.assertRaises(ValueError):
                validate_word("I", did, LEXICON)

    def test_unknown_words_and_token_bypasses_are_rejected(self):
        for word in ("notindictionary", "I I", "I\n", "I--", "I!!", "1", "І", "", None):
            with self.subTest(word=word), self.assertRaises(ValueError):
                word_syllables(word, LEXICON)

    def test_largest_pronunciation_count_is_used(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "dict"
            path.write_text(";;; comment\n# comment\nTEST T EH1 S T\n"
                            "TEST(2) T EH1 S AH0 T # variant\n")
            self.assertEqual(read_lexicon(path), {"test": 2})
            path.write_text("# no usable pronunciations\n")
            with self.assertRaisesRegex(ValueError, "no usable"):
                read_lexicon(path)


class FormTests(unittest.TestCase):
    def test_exact_ten_and_overflow(self):
        self.assertEqual(validate_poem(poem_with(), LEXICON, exact_ten=True), [10] * 14)
        self.assertEqual(validate_poem(poem_with(words=9), LEXICON), [9] * 14)
        for poem in (poem_with(words=9), poem_with(words=11), poem_with(lines=13),
                     poem_with(lines=15), poem_with().replace("I I", "I  I", 1)):
            with self.subTest(poem=poem[:20]), self.assertRaises(ValueError):
                validate_poem(poem, LEXICON, exact_ten=True)

    def test_stanza_boundaries_and_terminal_newline(self):
        lines = poem_with().splitlines()
        text = "\n\n".join("\n".join(lines[a:b]) for a, b in ((0, 4), (4, 8), (8, 12), (12, 14)))
        self.assertEqual(validate_poem(text + "\n", LEXICON, exact_ten=True), [10] * 14)
        with self.assertRaisesRegex(ValueError, "stanzas"):
            validate_poem("\n\n".join(("\n".join(lines[:7]), "\n".join(lines[7:]))), LEXICON)

    def test_example_with_shipped_dictionary(self):
        lexicon = read_lexicon(ROOT / "cmudict.dict")
        self.assertGreater(len(lexicon), 100_000)
        self.assertEqual(validate_poem((ROOT / "examples/format-poem.txt").read_text(),
                                       lexicon, exact_ten=True), [10] * 14)


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.addCleanup(self.db.close)
        self.db.create_function("word_syllables", 1, lambda word: word_syllables(word, LEXICON),
                                deterministic=True)
        self.db.create_function("validate_word", 2, lambda word, did: validate_word(word, did, LEXICON),
                                deterministic=True)
        self.db.executescript((ROOT / "sonnet_format.sql").read_text())

    def add(self, turn, did=DID_A, word="I", line=1, game="game-a"):
        self.db.execute("INSERT INTO sonnet_words VALUES (?, ?, ?, ?, ?)",
                        (game, turn, line, did, word))

    def test_turn_order_repeat_participation_and_immutability(self):
        self.add(1)
        with self.assertRaisesRegex(sqlite3.IntegrityError, "consecutive"):
            self.add(2, line=2)
        self.add(2, DID_B)
        self.add(3, DID_A)
        with self.assertRaisesRegex(sqlite3.IntegrityError, "advance"):
            self.add(2, DID_B)
        for sql in ("UPDATE sonnet_words SET token = 'the'",
                    "DELETE FROM sonnet_words",
                    "INSERT OR REPLACE INTO sonnet_words VALUES ('game-a', 1, 1, ?, 'I')"):
            with self.subTest(sql=sql), self.assertRaises(sqlite3.IntegrityError):
                self.db.execute(sql, (DID_B,) if "?" in sql else ())
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM sonnet_words").fetchone()[0], 3)

    def test_overflow_and_games_are_independent(self):
        for turn in range(1, 11):
            self.add(turn, DID_A if turn % 2 else DID_B)
        with self.assertRaisesRegex(sqlite3.IntegrityError, "exceeds 10"):
            self.add(11)
        self.add(11, line=2)
        self.add(1, game="game-b")

    def test_dictionary_and_did_checks_cannot_be_bypassed(self):
        for did, word in ((DID_A, "wool"), (DID_A, "I I"), ("agent-a", "I")):
            with self.subTest(did=did, word=word), self.assertRaises(sqlite3.DatabaseError):
                self.add(1, did, word)

    def test_participation_floor_and_ceiling(self):
        # Syntax fixtures only: the SQL example does not authenticate public keys.
        for number, final_character in enumerate("abcdefghi", 1):
            self.add(number, DID_A[:-1] + final_character)
            if number in (3, 4, 8, 9):
                count, valid = self.db.execute("SELECT contributors, valid FROM sonnet_participation").fetchone()
                self.assertEqual(count, number)
                self.assertEqual(valid, int(4 <= number <= 8))


if __name__ == "__main__":
    unittest.main()
