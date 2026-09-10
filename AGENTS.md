# Working on technocore-sonnet

The rules and canonical validator/SQL blocks live in `sonnet-game.md`.
Edit those blocks, then run `python3 scripts/build.py` to regenerate their
standalone files and `manifest.json`. Do not edit generated files directly.

The dictionary and its original license are frozen to the revision and hashes
in `upstream.json`. Do not silently replace either file. Any approved dictionary
change requires updating the provenance, the rule document's hash, and the
manifest together, and creates a new contest package version.

Validate changes with:

```sh
python3 scripts/build.py --check
python3 scripts/verify.py
python3 -m unittest discover -s tests -v
```

The package is a draft. Publishing repository changes, posting messages, creating
live rooms, posting to X, and sending payments require explicit user authorization.
Keep credentials, signing seeds, ballots, and participant data out of this repo.
