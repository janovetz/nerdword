# Nerdword

A swipe-to-spell crossword word game in a single page. Connect letters on the wheel to fill the grid, find bonus words, and remember to pay the Jake Tax.

Play it at https://janovetz.github.io/nerdword/

- `index.html`: the whole game, with no build step
- `puzzles.js`: 600 generated levels
- `tools/generate_levels.py`: regenerates `puzzles.js` (`python3 tools/generate_levels.py --levels 600`); it downloads its word lists into `tools/data/` on the first run

Testing helpers: `?jaketax` forces the Jake Tax, and `?today=YYYY-MM-DD` pretends it's another date.
