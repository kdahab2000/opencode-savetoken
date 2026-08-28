# Publishing this repository later

This repo was created locally and never pushed. When you are ready:

1. Review the tree one more time:
   `python3 -m unittest discover -s tests -v` and
   `grep -rn "BEGIN.*PRIVATE KEY" . || true`.
2. Create the remote (e.g. GitHub `opencode-savetoken`) and:
   ```sh
   git remote add origin <url>
   git push -u origin main
   ```
3. Tag a version: `git tag -a v0.1.0 -m "initial integration kit" && git push --tags`.
4. Release checklist: LICENSE/NOTICE current; provenance headers intact;
   no personal absolute paths (enforced by tests/test_packaging.py); the
   pinned SaveToken dependency path documented in README; model docs
   reflect currently verified capabilities only.

Note: the pinned dependency is the *SaveToken* repository. If you publish
this repo publicly, either publish SaveToken first or vendor the engine
consciously (that trade-off is discussed in the README).
