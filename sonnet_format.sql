-- Draft format constraints, NOT a complete game referee. Initialize once.
-- Register word_syllables(token) and validate_word(token, did) on every connection.
-- All connections must use the same immutable dictionary for this database.
-- agent_did must come from an authenticated, registered sender, not a claimed name.
CREATE TABLE sonnet_words (
    game_id TEXT NOT NULL CHECK(length(game_id) > 0),
    turn_no INTEGER NOT NULL CHECK(turn_no >= 1),
    line_no INTEGER NOT NULL CHECK(line_no BETWEEN 1 AND 14),
    agent_did TEXT NOT NULL CHECK(length(agent_did) > 0),
    token TEXT NOT NULL CHECK(validate_word(token, agent_did) BETWEEN 1 AND 10),
    PRIMARY KEY (game_id, turn_no)
) STRICT;

-- Explicit guards also refuse INSERT OR REPLACE, which could otherwise delete
-- the earlier contribution before inserting a replacement.
CREATE TRIGGER sonnet_turn_order
BEFORE INSERT ON sonnet_words
BEGIN
    SELECT CASE WHEN NEW.turn_no <= (
        SELECT COALESCE(MAX(turn_no), 0) FROM sonnet_words
        WHERE game_id = NEW.game_id
    ) THEN RAISE(ABORT, 'turn: must advance past the last accepted turn') END;
    SELECT CASE WHEN NEW.agent_did = (
        SELECT agent_did FROM sonnet_words WHERE game_id = NEW.game_id
        ORDER BY turn_no DESC LIMIT 1
    ) THEN RAISE(ABORT, 'agent: cannot contribute consecutive words') END;
END;

CREATE TRIGGER sonnet_line_budget
BEFORE INSERT ON sonnet_words
BEGIN
    SELECT CASE WHEN (
        SELECT COALESCE(SUM(word_syllables(token)), 0)
        FROM sonnet_words
        WHERE game_id = NEW.game_id AND line_no = NEW.line_no
    ) + word_syllables(NEW.token) > 10
    THEN RAISE(ABORT, 'line: exceeds 10 syllables') END;
END;

CREATE TRIGGER sonnet_no_update
BEFORE UPDATE ON sonnet_words
BEGIN
    SELECT RAISE(ABORT, 'word: accepted contributions are immutable');
END;

CREATE TRIGGER sonnet_no_delete
BEFORE DELETE ON sonnet_words
BEGIN
    SELECT RAISE(ABORT, 'word: accepted contributions are immutable');
END;

-- Evaluate only on the finished poem: opening moves cannot meet the minimum count.
-- The referee must also compare these contributors to the frozen roster and
-- check their signatures. Claimed agent_did strings alone establish no identity.
CREATE VIEW sonnet_participation AS
SELECT game_id, COUNT(DISTINCT agent_did) AS contributors, COUNT(*) AS total_words,
       COUNT(DISTINCT agent_did) BETWEEN 4 AND 8 AS valid
FROM sonnet_words
GROUP BY game_id;

-- Final participation precheck: require one result row with valid = 1.
-- SELECT * FROM sonnet_participation WHERE game_id = ?;
-- Whole-poem length precheck (does not establish line order or closure):
-- SELECT COUNT(*) = 14 AND MIN(syllables) = 10 AND MAX(syllables) = 10 AS valid
-- FROM (
--     SELECT line_no, SUM(word_syllables(token)) AS syllables
--     FROM sonnet_words WHERE game_id = ? GROUP BY line_no
-- );
