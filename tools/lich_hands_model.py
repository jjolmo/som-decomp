"""Tick-level model of the Dark Lich's phase machine, written only from the selection rules read in the ROM (docs/dark-lich.md section 4 and
docs/dark-lich-hands.md), used to check that the observed number of actions per phase and the phase lengths agree.
usage: lich_hands_model.py [PHASES] [P_DIR13] [SEED] [P_LEAVE_BODY] [P_LEAVE_HANDS]      no ROM needed (the leave chance of the ROM rule is 0.2 per call)
Rules (all durations in ticks of 5 frames):
  AD counts ticks since the last action ended; threshold 49. A state of mode 1 is cut as soon as AD >= 49; mode 0 states and transitions are never cut.
  body chooser: 20% -> transition 18,19,1A (37+37+1); otherwise stand/walk 37 ticks. Action when AD >= 49: projectile 37 ticks, spell 11-17 ticks, alternating
  (first = projectile). hands chooser (bit15 clear): 20% -> 1B,1C,1D (37+37+1); else direction code 1/3 (probability P_DIR13) -> 1F/26 25 ticks,
  otherwise 1E (37 ticks) or 20 (4 ticks, sets bit15) with probability 1/2. Hands chooser (bit15 set): 21 (until AD >= 49, then 1 tick per call) or
  23 (4 ticks, clears bit15) with probability 1/2, or 22/27 25 ticks for direction codes 1/3. Hands action (bit15 clear): slam 24, 17 ticks."""
import sys, random

SPELL_TICKS = (11, 14, 13, 14, 12, 17, 15)
THR = 49


def cut(run, ad):
    """A mode-1 state of RUN ticks entered with action counter AD is cut as soon as AD reaches the threshold."""
    return max(1, min(run, THR - ad + 1))


def simulate(n_phases, p_dir13, rnd, p_leave_body=0.2, p_leave_hands=0.2):
    body = []; hands = []
    for _ in range(n_phases):
        t = 0; acts = 0; raised = False; ad = THR              # body phase: the first action follows at once
        while True:
            if ad >= THR:                                      # action routine: bit15 toggles, projectile when it becomes set
                raised = not raised
                t += 37 if raised else SPELL_TICKS[rnd.randrange(7)]; acts += 1; ad = 0; continue
            if rnd.random() < p_leave_body: break              # chooser: body -> hands transition
            run = cut(37, ad); t += run; ad += run
        body.append((t, acts))
        t = 0; acts = 0; raised = False; ad = THR              # hands phase: the slam follows at once
        while True:
            if ad >= THR and not raised:                       # action routine: slam
                t += 17; acts += 1; ad = 0; continue
            if not raised and rnd.random() < p_leave_hands: break   # chooser with bit15 clear: hands -> body transition
            d13 = rnd.random() < p_dir13
            if not raised:
                if d13: run = cut(25, ad)                      # 1F / 26
                elif rnd.random() < 0.5: run = cut(37, ad)     # 1E
                else: run = cut(4, ad); raised = True          # 20 raises the hands
            else:
                if d13: run = cut(25, ad)                      # 22 / 27
                elif rnd.random() < 0.5: run = cut(10 ** 6, ad)   # 21: until AD reaches the threshold (1 tick when it already has)
                else: run = cut(4, ad); raised = False         # 23 lowers the hands
            t += run; ad += run
        hands.append((t, acts))
    return body, hands


def stats(v):
    return len(v), min(v), sum(v) / len(v), max(v)


if __name__ == '__main__':
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 100000
    p13 = float(sys.argv[2]) if len(sys.argv) > 2 else 0.15
    rnd = random.Random(int(sys.argv[3]) if len(sys.argv) > 3 else 1)
    pb = float(sys.argv[4]) if len(sys.argv) > 4 else 0.2
    ph = float(sys.argv[5]) if len(sys.argv) > 5 else 0.2
    body, hands = simulate(n, p13, rnd, pb, ph)
    for name, v in (('body', body), ('hands', hands)):
        s_t = stats([t * 5 / 60.0988 for t, _ in v]); s_a = stats([a for _, a in v])
        print('%-5s seconds n=%d min=%.2f mean=%.2f max=%.2f   actions n=%d min=%d mean=%.3f max=%d' % ((name,) + s_t + s_a))
