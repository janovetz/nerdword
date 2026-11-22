#!/usr/bin/env python3
"""
Generate the level data (puzzles.js) for Nerdword.

Each level is a set of wheel letters, a small crossword of common words that
can be spelled from those letters, and a list of extra valid "bonus" words.

Word lists (downloaded into tools/data on first run):
  - google-10000-english (no swears) + 20k : commonness ranking for grid words
  - ENABLE                                 : the broad dictionary for bonus words
  - LDNOOBW                                : blocklist

Usage:  python3 tools/generate_levels.py [--levels 600] [--seed 7]
"""
import argparse
import json
import os
import random
import urllib.request
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
OUT = os.path.join(HERE, "..", "puzzles.js")

SOURCES = {
    "common10k.txt": "https://raw.githubusercontent.com/first20hours/google-10000-english/master/google-10000-english-usa-no-swears.txt",
    "common20k.txt": "https://raw.githubusercontent.com/first20hours/google-10000-english/master/20k.txt",
    "enable.txt": "https://raw.githubusercontent.com/dolph/dictionary/master/enable1.txt",
    "bad.txt": "https://raw.githubusercontent.com/LDNOOBW/List-of-Dirty-Naughty-Obscene-and-Otherwise-Bad-Words/master/en",
}

# Extra words kept out of grids and bonus lists (abbreviations, slangy or awkward stuff
# that sneaks into frequency lists).
EXTRA_BLOCK = set("""
ass asses arse cum tit tits sex sexy sexes porn porno nude nudes rape raped rapes
nazi nazis kill kills killer gun guns drug drugs dick dicks cock cocks fag fags
hell damn crap pee pees poo poop piss homo homos hoe hoes bra bras gay gays
fucks pussies condoms orgies peeing butts sucked gagged hogtied escorts thongs preteen virgins
""".split())

# Real words, but not ones we want as crossword answers (names, abbreviations, web jargon).
GRID_BLOCK = set("""
web jun mon tel mac max las tom ads lee sec del joe ave pic var rom ben lib cam ref res bio med biz
reg rep sri lat rev cad eng chi ins dos gen alt hon sox mem mag rec phi ons abs sim sol col dis kay
ser nam mas dom cos pac ana eau mil ala dow dui yen til pix pam leu dee mae mel sic sen ids att als
lin het mol ems rem cis rex mis lea nos wap ops huh hmm ret sup pol mos vis cor ars mib cur lam ich
goa sis tas vac nan mus eff tor ole tis lac bel sha bis hep wat yay jew ras ers ama aba tao heh eta
kos tau kat sos bro lei deb tho gee ors lex roc pow gan ted mod amp psi pas bot sac bur yep ups per
cad gal doc dev
info teen john pics logo mike hong null beta dell tony matt euro dean visa babe demo alan jane char
nick para semi kent hist anna nova rick marc meta carl temp lite brad thru jews cole mart docs cams
spec midi comp dale sept lang stud glen chad josh ciao prep mono nuke troy sims hart shaw expo soma
earl sync mesa rand beth jill jake libs exec mods fuji casa carb blah keno gage kirk spas mama joey
bach khan cola gals olds duff prof haha maya papa peso vera cote gran mayo lowe coca fave alfa puma
carr pooh roms lima prog hank fiat noel noir alma holt faux alba dong berg tyne luna tiff macs acta
yuan tate kris regs otto mick tele phat toby cobb toon lars viva howe vail shah alps zeta auto anti
java mini ford ness aero eddy sans gore aqua lieu wont oops yang bios secs subs ritz deco jerk hunk
texas peter paris jones louis harry kelly wales henry devel babes lewis roger kerry maria trans terry
jerry laura billy nancy jimmy ralph perry tommy congo butts bobby colin randy donna devon jesse euros
leone xerox johns teddy logan romeo turks nelly brent shawn celeb woody molly supra pedro evite terra
bates welch mikes jacks ariel avant mafia femme hicks macon cocos patty
amazon martin alaska joseph jordan oxford morgan thongs johnny cyprus carter graham warren morris
rogers peeing danish arabic brooks victor gibson latino gothic celebs pierce apollo peters orgies
davies mickey toledo fedora romans gloria bonnie regina nordic laguna afghan brasil sheila pascal
cairns caesar gentoo quinta sucked gagged dalton psycho browns reeves freaks
english lesbian siemens bristol charlie holland madonna baptist timothy escorts spencer hamburg
hogtied cologne robbins riviera condoms pussies preteen virgins broncos bologna vikings germans
kashmir sapiens espanol parsons gigabit bombing killers
""".split())


def load_lists():
    os.makedirs(DATA, exist_ok=True)
    for name, url in SOURCES.items():
        path = os.path.join(DATA, name)
        if not os.path.exists(path):
            print("downloading", name)
            urllib.request.urlretrieve(url, path)

    def read(name):
        with open(os.path.join(DATA, name), encoding="utf-8", errors="ignore") as f:
            return [w.strip().lower() for w in f if w.strip()]

    enable = set(read("enable.txt"))
    bad = set(w for w in read("bad.txt") if " " not in w) | EXTRA_BLOCK
    ok = lambda w: w.isalpha() and w.isascii() and 3 <= len(w) <= 7 and w in enable and w not in bad

    rank = {}
    for i, w in enumerate(read("common10k.txt")):
        if ok(w) and w not in rank and w not in GRID_BLOCK:
            rank[w] = i
    # second tier: the 20k list, but only past the 10k (already covered) and capped
    swears_10k = set(read("common20k.txt")[:10000]) - set(read("common10k.txt"))
    for i, w in enumerate(read("common20k.txt")[:16000]):
        if ok(w) and w not in rank and w not in swears_10k and w not in GRID_BLOCK:
            rank[w] = 10000 + i
    dictionary = set(w for w in enable if ok(w))
    return rank, dictionary


def fits(word, pool):
    need = Counter(word)
    return all(pool[ch] >= n for ch, n in need.items())


# ---------------------------------------------------------------- crossword layout

class Layout:
    def __init__(self):
        self.cells = {}  # (r,c) -> letter
        self.dirs = {}   # (r,c) -> set('h','v')
        self.words = []  # (word, r, c, d)

    def copy(self):
        o = Layout()
        o.cells = dict(self.cells)
        o.dirs = {k: set(v) for k, v in self.dirs.items()}
        o.words = list(self.words)
        return o

    def bbox(self):
        rs = [r for r, _ in self.cells]
        cs = [c for _, c in self.cells]
        return min(rs), min(cs), max(rs), max(cs)

    def check(self, word, r, c, d):
        """Return number of crossings if the placement is legal, else -1."""
        dr, dc = (0, 1) if d == "h" else (1, 0)
        if (r - dr, c - dc) in self.cells:
            return -1
        if (r + dr * len(word), c + dc * len(word)) in self.cells:
            return -1
        cross = 0
        for i, ch in enumerate(word):
            p = (r + dr * i, c + dc * i)
            if p in self.cells:
                if self.cells[p] != ch or d in self.dirs[p]:
                    return -1
                cross += 1
            else:
                # perpendicular neighbours must be empty so no accidental words appear
                for s in (-1, 1):
                    q = (p[0] + dc * s, p[1] + dr * s)
                    if q in self.cells:
                        return -1
        return cross

    def place(self, word, r, c, d):
        dr, dc = (0, 1) if d == "h" else (1, 0)
        for i, ch in enumerate(word):
            p = (r + dr * i, c + dc * i)
            self.cells[p] = ch
            self.dirs.setdefault(p, set()).add(d)
        self.words.append((word, r, c, d))

    def candidates(self, word):
        out = []
        for (pr, pc), ch in self.cells.items():
            for i, wch in enumerate(word):
                if wch != ch:
                    continue
                for d in ("h", "v"):
                    if d in self.dirs[(pr, pc)]:
                        continue
                    r, c = (pr, pc - i) if d == "h" else (pr - i, pc)
                    x = self.check(word, r, c, d)
                    if x > 0:
                        out.append((x, r, c, d))
        return list(set(out))


def build_layout(words, target, max_side, rng, tries=40):
    """words[0] is the anchor (full-length word). Returns best Layout found."""
    best, best_key = None, None
    others = words[1:]
    for t in range(tries):
        lay = Layout()
        lay.place(words[0], 0, 0, "h" if rng.random() < 0.6 else "v")
        # mostly keep preference order, with some jitter
        pool = [w for _, w in sorted((i + rng.random() * 4, w) for i, w in enumerate(others))]
        for w in pool:
            if len(lay.words) >= target:
                break
            opts = []
            for x, r, c, d in lay.candidates(w):
                trial_cells = list(lay.cells) + [
                    (r + (0 if d == "h" else i), c + (i if d == "h" else 0)) for i in range(len(w))
                ]
                rs = [p[0] for p in trial_cells]
                cs = [p[1] for p in trial_cells]
                h, wd = max(rs) - min(rs) + 1, max(cs) - min(cs) + 1
                if h > max_side or wd > max_side:
                    continue
                score = x * 6 - (h * wd) * 0.35 - abs(h - wd) * 0.8 + rng.random() * 2
                opts.append((score, r, c, d))
            if opts:
                opts.sort(reverse=True)
                _, r, c, d = opts[0]
                lay.place(w, r, c, d)
        r0, c0, r1, c1 = lay.bbox()
        h, wd = r1 - r0 + 1, c1 - c0 + 1
        crossings = sum(1 for v in lay.dirs.values() if len(v) == 2)
        key = (len(lay.words), crossings * 0.5 - h * wd * 0.05 - abs(h - wd) * 0.3)
        if best_key is None or key > best_key:
            best, best_key = lay, key
        if len(lay.words) >= target and t > 12:
            break
    return best


# ---------------------------------------------------------------- level plan

def tier_for(level):
    """(letters, min_words, max_words, max_side)"""
    if level <= 3:
        return 3, 2, 3, 5
    if level <= 15:
        return 4, 3, 5, 6
    if level <= 45:
        return 5, 4, 6, 7
    if level <= 140:
        return 6, 5, 8, 9
    # later: mostly seven, sometimes six for rhythm
    if level % 7 == 3:
        return 6, 6, 9, 9
    return 7, 6, 11, 10


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--levels", type=int, default=600)
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()
    rng = random.Random(args.seed)

    rank, dictionary = load_lists()
    common = sorted(rank, key=rank.get)
    by_len = {}
    for w in common:
        by_len.setdefault(len(w), []).append(w)

    used_sets = set()
    levels = []
    level = 1
    # per-length cursor into a shuffled list of bases; easier (more common) words come first
    queues = {}
    for n in range(3, 8):
        lst = by_len.get(n, [])[:]
        # blend: sort by rank but jitter so it's not strictly frequency-ordered
        lst.sort(key=lambda w: rank[w] * (0.6 + rng.random() * 0.8))
        queues[n] = lst

    while level <= args.levels:
        n, kmin, kmax, max_side = tier_for(level)
        q = queues[n]
        made = False
        while q:
            base = q.pop(0)
            key = "".join(sorted(base))
            if key in used_sets:
                continue
            pool = Counter(base)
            grid_cands = [w for w in common if len(w) <= n and fits(w, pool)]
            if len(grid_cands) < kmin:
                continue
            full = [w for w in grid_cands if len(w) == n]
            anchor = base
            rest = [w for w in grid_cands if w != anchor]
            # preference: other full-length words, then longer & more common words
            rest.sort(key=lambda w: (-(len(w) == n), rank[w] / 2500 - len(w) * 0.6 + rng.random() * 1.2))
            target = rng.randint(kmin, kmax)
            lay = build_layout([anchor] + rest, target, max_side, rng)
            if lay is None or len(lay.words) < kmin:
                continue
            used_sets.add(key)
            r0, c0, r1, c1 = lay.bbox()
            words = sorted(
                [(w, r - r0, c - c0, d) for w, r, c, d in lay.words],
                key=lambda x: (len(x[0]), x[0]),
            )
            placed = {w for w, *_ in words}
            bonus = sorted(w for w in dictionary if len(w) <= n and w not in placed and fits(w, pool))
            letters = list(base)
            for _ in range(20):
                rng.shuffle(letters)
                if "".join(letters) not in placed:
                    break
            levels.append({
                "l": "".join(letters).upper(),
                "rows": r1 - r0 + 1,
                "cols": c1 - c0 + 1,
                "w": ["%s,%d,%d,%s" % (w.upper(), r, c, d) for w, r, c, d in words],
                "b": " ".join(bonus).upper(),
            })
            made = True
            break
        if not made:
            raise SystemExit("ran out of base words at level %d (n=%d)" % (level, n))
        level += 1

    with open(OUT, "w") as f:
        f.write("// Generated by tools/generate_levels.py -- do not edit by hand.\n")
        f.write("window.WW_LEVELS = ")
        json.dump(levels, f, separators=(",", ":"))
        f.write(";\n")

    sizes = Counter(len(l["w"]) for l in levels)
    print("wrote", len(levels), "levels to", os.path.normpath(OUT))
    print("words per level:", dict(sorted(sizes.items())))
    print("max grid:", max(l["rows"] for l in levels), "x", max(l["cols"] for l in levels))
    print("size: %.0f KB" % (os.path.getsize(OUT) / 1024))


if __name__ == "__main__":
    main()
