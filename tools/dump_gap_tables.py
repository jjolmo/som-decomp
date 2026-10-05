"""Dump the second batch of gameplay tables to JSON (numbers only: no graphics, no text).
usage: dump_gap_tables.py ROM STATE OUTDIR
  drops.json          monster drop rows decoded (chance, trap threshold, content rule, item/gold bytes, outcome probabilities)
  item_effects.json   consumable effects measured by running the real item routine $C0:54E7 on a save-state hero
  weapon_levels.json  weapon level-up constants (thresholds, orb prices, caps, charge timing measured on $C0:B330)
  status_effects.json status bits: timer groups, exclusivity cascade, sources found in the tables, immunity statistics
  prices.json         shop price tables (consumables, armor rows, orb levels)
STATE is a ZSNES save state (WRAM source for the harness). Item effects and charge timing are executed; the rest is read from ROM.
Layout and meaning of every field: docs/rom-combat.md sections 13-18."""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import combat_env as ce


def u16(d, o): return d[o] | d[o + 1] << 8


def decode_item_byte(v):
    """Item byte of a drop row (same encoding as the inventory-add routine $C0:6420)."""
    if v < 0x15: return dict(kind='armor', armor_row=v, slot='head')
    if v < 0x2A: return dict(kind='armor', armor_row=v, slot='body')
    if v < 0x3F: return dict(kind='armor', armor_row=v, slot='accessory')
    if 0x40 <= v < 0x4C: return dict(kind='consumable', id=v - 0x40)
    if 0x80 <= v < 0x88: return dict(kind='weapon_orb', weapon_type=v - 0x80, fallback_if_type_maxed=dict(kind='consumable', id=0))
    return dict(kind='unknown', raw=v)


def drops(rom):
    rows = []
    for mid in range(0x57):
        r = list(rom[0x103A50 + mid * 5: 0x103A50 + mid * 5 + 5])
        if r[0] == 0xFF:
            continue
        b0, b1, b2, b3, b4 = r
        chance = b0 & 0x3F
        always = bool(b0 & 0x40)
        p_drop = 1.0 if always else chance / 64.0
        a4 = (b2 >> 3) & 7                    # content roll threshold: r = rnd & 63, carry = r >= a4
        p_hi = (64 - a4) / 64.0               # probability of byte 3 (carry set)
        mode = b2 >> 6
        kinds = {0: ('gold', 'gold'), 1: ('item', 'item'), 2: ('gold', 'item'), 3: ('item', 'gold')}[mode]
        def pack(kind, v):
            return dict(kind='gold', amount=v) if kind == 'gold' else decode_item_byte(v)
        contents = [dict(probability=round(p_hi, 6), **pack(kinds[0], b3)), dict(probability=round(1 - p_hi, 6), **pack(kinds[1], b4))]
        rows.append(dict(monster_id=mid, raw=r, p_chest=round(p_drop, 6), chance_64=chance, always=always, flag_bit7=bool(b0 & 0x80),
                         trap_agi_threshold=(b1 & 0xF0) >> 1, byte1_low_nibble=b1 & 15, content_roll_threshold=a4, content_mode=mode, contents=contents))
    return rows


def item_effects(rom, state):
    out = []
    FIELDS = (0x182, 0x190, 0x191, 0x1B2, 0x1B3, 0x1B4, 0x1B5, 0x1B6, 0x1F3, 0x1F6)
    for item in range(12):
        env = ce.Env(rom, state); h = env.obj(0)
        h.sw(0x184, 500); h.sw(0x182, 100); h.sb(0x186, 10); h.sb(0x187, 50); h.sw(0x1AA, 0)
        h.sw(0x190, 0x2110)                                       # sleep + poison + balloon, alive
        for f in (0x1B0, 0x1B1, 0x1B2, 0x1B3, 0x1B4, 0x1B5, 0x1B6, 0x1F1, 0x1F2, 0x1F3, 0x1F4, 0x1F5, 0x1F6): h.sb(f, 0)
        h.sb(0x191, 0)
        b = {f: h.b(f) for f in FIELDS}; bw = {f: h.w(f) for f in (0x182, 0x190, 0x1F3)}
        env.call(0xC054E7, A=item, X=0, m=1, x=0, D=0x300)
        env2 = ce.Env(rom, state); g = env2.obj(0)
        g.sw(0x184, 500); g.sw(0x182, 0); g.sw(0x190, 0x8000); g.sb(0x191, 0x80); g.sw(0x1AA, 0)
        for f in (0x1B0, 0x1B1, 0x1F1, 0x1F2, 0x1F3, 0x1F4, 0x1F5, 0x1F6): g.sb(f, 0)
        env2.call(0xC054E7, A=item, X=0, m=1, x=0, D=0x300)
        e = dict(id=item,
                 pending_hp_heal=h.w(0x1F3), pending_hp_heal_is_max_hp=h.w(0x1F3) == 500, pending_mp_heal=h.b(0x1F6),
                 status_word_after=h.w(0x190), clears_status_word=bool(bw[0x190] and h.w(0x190) == 0), e191_after=h.b(0x191),
                 timers_set=[h.b(0x1B2 + i) for i in range(5)] if any(h.b(0x1B2 + i) for i in range(5)) else None,
                 on_dead_hero=dict(hp_after=g.w(0x182), e191_after=g.b(0x191), pending_hp_heal=g.w(0x1F3)))
        out.append(e)
    return out


STATUS_BITS = [
    # (bit, timer byte, effect as read in the code). Sources (spells, weapon rows, attack rows) are listed by status_effects().
    (0x0004, 0x1B2, 'accuracy -1/16 in the hit test (E190 bit 2)'),
    (0x0008, 0x1B2, 'Agi -1/16 in the stat build (E190 bit 3); no spell/attack row sets it'),
    (0x0010, 0x1B2, 'cleared by any damaging hit ($C0:5119); crit chance x2 against it; sets E1B1 bit 0'),
    (0x0020, 0x1B2, 'cannot act (mask C160 in the input handler)'),
    (0x0040, 0x1B2, 'cannot act (mask C160), HP -> HP/2+1 when applied, cascade keeps 0x9AC0'),
    (0x0080, 0x1B3, 'effect not determined'),
    (0x0100, 0x1B3, 'cannot act, sprite size depends on the spell level (<4, <8, 8)'),
    (0x0200, None, 'own damage forced to 1, defense /4; no timer'),
    (0x0400, None, 'no hits resolved on the actor ($C0:4F7B); no timer'),
    (0x0800, 0x1B5, 'monsters take one of 8 random sprites; heroes are always immune (0x0800 in the hero immunity word)'),
    (0x1000, 0x1B5, 'sprite offset +0x70'),
    (0x2000, 0x1B6, '1 HP per timer drop, ends at HP 1'),
    (0x4000, 0x1B6, '1 HP per timer drop, ends at HP 1; cannot act (mask C160); removes the 0x2000 bit'),
    (0x8000, None, 'KO flag; clears every other bit when applied; removed by item routine $C0:54E7 id 5 and spell handler ED04'),
]


def status_effects(rom):
    spells = [dict(id=i, status=u16(rom, 0x102AD0 + i * 64 + 13)) for i in range(42)]
    weapons = [dict(id=i, status=u16(rom, 0x101000 + i * 12 + 9), chance=rom[0x101000 + i * 12 + 11]) for i in range(256)]
    boss = [dict(id=i, status=u16(rom, 0x10BDC1 + i * 7 + 4), chance=rom[0x10BDC1 + i * 7 + 6]) for i in range(115)]
    armors = [dict(id=i, mask=u16(rom, 0x103ED0 + i * 10 + 7)) for i in range(63)]
    mons = [u16(rom, 0x101C00 + i * 29 + 20) for i in range(128)]
    bits = []
    for bit, timer, effect in STATUS_BITS:
        bits.append(dict(mask=bit, effect=effect, timer_byte=timer,
                         spell_ids=[x['id'] for x in spells if x['status'] & bit],
                         player_weapon_rows=[x['id'] for x in weapons[:72] if x['status'] & bit],
                         monster_attack_rows=sorted(set((x['id'], x['chance']) for x in weapons[72:] if x['status'] & bit)),
                         boss_attack_rows=[(x['id'], x['chance']) for x in boss if x['status'] & bit],
                         armor_rows_immune=[x['id'] for x in armors if x['mask'] & bit], monsters_immune=sum(1 for m in mons[:128] if m & bit)))
    return dict(
        source='$C8:E301 (apply), E3A9 (duration), E487/E4D7/E50F (exclusivity), $C0:3C19-3DCD (timers), $C0:5119 (weapon status roll). word = E191<<8 | E190',
        bits=bits,
        timer_groups=[dict(timer_byte=0x1B2, bits=0x007C), dict(timer_byte=0x1B3, bits=0x0180), dict(timer_byte=0x1B5, bits_assigned=0x1C00, bits_counted_down=0x1800), dict(timer_byte=0x1B6, bits=0x6000)],
        duration_formula='d = max(20, low byte of ((damage_before_defense >> 2) - (magic_defense >> 1))); 20 when the difference is negative; spells use the spell power byte as damage_before_defense',
        timer_tick='every 4th call of the per-actor combat tick $C0:3A79 (first drop on call 1): lifetime = 4*d - 3 calls; tick rate: see docs/rom-combat.md section 1.3',
        dot=dict(bits=0x6000, hp_per_timer_drop=1, stops_at_hp=1),
        exclusivity=[dict(trigger=0x0040, keep_mask=0x9AC0), dict(trigger=0x0020, keep_mask=0x9AE0), dict(trigger=0x0010, keep_mask=0xFBF0), dict(trigger=0x0008, keep_mask=0xFBF0),
                     dict(trigger=0x0004, keep_mask=0xFFFC), dict(trigger=0x1000, keep_mask=0x92FF), dict(trigger=0x0800, keep_mask_if_0260=0xF7FF, keep_mask_else=0x9A13),
                     dict(trigger=0x0400, keep_mask_if_617B=0xFBFF), dict(trigger=0x4000, keep_mask=0xDAFF), dict(trigger=0x2000, keep_mask_if_1860=0xDFFF)],
        weapon_inflicted='attacker word & defender immunity != 0 -> nothing; else rnd(100) < chance% and damage > 0 -> word queued ($9A)',
        spell_inflicted='always applied (immune bits removed bitwise) on the first hit of the cast',
        hero_immunity='OR of the three armor status words | 0x0800')


def prices(rom):
    out = {}
    ents = [(u16(rom, 0x18FB84 + 6 * i), u16(rom, 0x18FB84 + 6 * i + 2), u16(rom, 0x18FB84 + 6 * i + 4)) for i in range(4)]
    names = {0xBA: ('consumable', 12), 0xA5: ('armor_accessory', 21), 0x90: ('armor_body', 21), 0x7B: ('armor_head', 21)}
    for start, base, ptr in ents:
        kind, n = names[start]
        out[kind] = dict(first_item_event_id=start, first_armor_row=base if kind.startswith('armor') else None,
                         prices=[u16(rom, 0x180000 + ptr + 2 * i) for i in range(n)])
    out['orb_by_level'] = [u16(rom, 0x18FCFB + 2 * i) for i in range(9)]
    out['note'] = 'range table at D8:FB84 (start id, base row, pointer); price = word at pointer + (id - start)*2; 65535 = not for sale; orb price indexed by the orb level already bought'
    return out


def main(rom, state, outdir):
    os.makedirs(outdir, exist_ok=True)
    def w(name, obj):
        with open(os.path.join(outdir, name), 'w') as f: json.dump(obj, f, indent=1); f.write('\n')
    w('drops.json', dict(source='drop row = 0x103A50 + monster_id*5 (5 bytes); rolled by $C0:4203 (death) and $C8:E0B0/$C8:E12C (chest opening). Probabilities assume the RNG byte is uniform.',
                         kill_class_table=list(rom[0x430D:0x4315]), rows=drops(rom)))
    w('item_effects.json', dict(source='measured by executing $C0:54E7 on hero 0 (500 max HP, 100 HP, 50 max MP) in a save state; ids = consumable index (0 first). Heal values are pending amounts, applied by $C0:4004 (capped at 999 and max HP; skipped for dead heroes).',
                                effect_bytes=[rom[0x104152 + i * 16] for i in range(12)], rows=item_effects(rom, state)))
    w('status_effects.json', status_effects(rom))
    w('prices.json', prices(rom))
    # weapon-level constants; charge timing is measured in tools/charge_timing.py (documented, not stored per run)
    w('weapon_levels.json', dict(
        source='$C0:4358 (level up), $C0:43AC (thresholds), $C0:7B9B shop/orb purchase, D8:FCFB price table, $C0:B330 charge gauge',
        progress_threshold_by_level=list(rom[0x43AC:0x43B5]), max_level=8, level_cap_rule='progress is frozen at 0 once level == orbs_bought[type] + 1; level 8 is the absolute maximum',
        progress_gain_formula='9 - weapon_level of the killer, halved when monster level < killer level; killer gets it, the other living heroes get half',
        orb_price_by_level=[u16(rom, 0x18FCFB + 2 * i) for i in range(9)], orb_price_note='65535 = cannot be bought (level 8)',
        charge=dict(calls_per_act=2, acts_per_stage=45, calls_per_stage=90, first_stage_call=89, unit='calls of the per-frame input handler $C0:B330, one per frame while the attack button is held',
                    seconds_per_stage_60fps=1.5, seconds_full_level8_60fps=11.98)))


if __name__ == '__main__':
    main(open(sys.argv[1], 'rb').read(), sys.argv[2], sys.argv[3])
