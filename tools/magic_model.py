"""Python model of the SoM spell hit resolution (damage spells), from $C8:E7A7 / E855 / E8A0 / E8C0 / E990 / E9DF (+ $C0:54B2, 543B).
Validated against the real ROM routines by validate_magic.py."""
def cap(v, m): return m if v > m else v
def spell_stat(c, spell):
    """$C8:E855: caster stat and (for monsters) spell power. spell id % 6 < 3 -> Int/E1FD, else Wis/E1FE"""
    if spell % 6 < 3: return c['INT'], c['E1FD']
    return c['WIS'], c['E1FE']
def target_mdef(t, rng):
    """$C8:E990 -> $94"""
    r = rng.below(0x65)
    md = t['MDEF']
    if r < t['MEV']:
        n = (md >> 4) & 0xFF
        return cap((md + rng.below(n)) & 0xFFFF, 999)
    a8 = (md + (md >> 2)) & 0xFFFF
    return (t['MEV'] * a8) // 100
def spell_damage(c, t, row, level, divisor, caster_is_hero, rng):
    """returns (damage_added_to_E1F1, mult8F). row = dict(power=row[10], acc=row[11], elem=row[12])"""
    stat, p96 = spell_stat(c, row['id'])
    if caster_is_hero: p96 = row['power']
    # element ($C8:E8A0)
    if row['elem'] & t['RES']: m8f = 1
    elif row['elem'] & t['WEAK']: m8f = 4
    else: m8f = 2
    d94 = target_mdef(t, rng)
    acc = cap(((stat >> 2) + row['acc']) & 0xFF, 99)      # 8-bit ADC, wraps above 255
    d4 = (p96 + stat) & 0xFF
    d0 = (level + 2) & 0xFF
    v = cap((d0 * d4) >> 1, 999)
    r = rng.below(0x65)
    if r >= acc:
        v = (acc * v) // 100
    else:
        v = (c['E6'] * c['E6'] + v) & 0xFFFF
        v = (v + rng.below((v >> 4) & 0xFF)) & 0xFFFF
    v = ((v * m8f) & 0xFFFF) >> 1
    v = v // divisor
    v = cap(v, 999)
    dmg = v - d94
    if dmg <= 0: dmg = 1
    return dmg, m8f

def heal_amount(c, t, row, level, divisor, caster_is_hero, rng):
    """Cure Water style handler ($C8:EBB3): $8F forced to 4, no defense subtraction: heal = $89 after E8C0 (E1F3 += $89).
    The RNG is still consumed by the target-defence roll in E990."""
    stat, p96 = spell_stat(c, row['id'])
    if caster_is_hero: p96 = row['power']
    target_mdef(t, rng)                       # E990 is run (and consumes randoms) even though $94 is unused
    acc = cap(((stat >> 2) + row['acc']) & 0xFF, 99)
    d4 = (p96 + stat) & 0xFF
    v = cap(((level + 2) * d4) >> 1, 999)
    r = rng.below(0x65)
    if r >= acc: v = (acc * v) // 100
    else:
        v = (c['E6'] * c['E6'] + v) & 0xFFFF
        v = (v + rng.below((v >> 4) & 0xFF)) & 0xFFFF
    v = ((v * 4) & 0xFFFF) >> 1
    return cap(v // divisor, 999)
