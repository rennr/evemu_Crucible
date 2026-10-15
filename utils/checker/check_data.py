#!/usr/bin/env python3
"""check_data.py - static data invariants for an EVEmu database.

Most of the bugs found in this server have not been logic errors.  They have been *missing data* that some
code path then read as zero, and the zero did something catastrophic and silent:

  * dunSpawnGroups.warpIn read as true (a text-protocol "0" whose first byte is '0', not 0) put every dungeon
    wave 100-150km off its beacon, in a bubble with no player in it, where it went dormant.  Sites looked empty.
  * The Imperial Navy Capacitor Power Relay has no shieldRechargeRateMultiplier (134), so the effects processor
    read 0 and multiplied the ship's shieldRechargeRate to zero.  CalcRechargeRate clamped that to 1ms, giving
    ~6,100,000 HP/s of passive regen:  the ship was unkillable and nothing said so.
  * dgmTypeAttributes has no rows at all for entityMaxWanderRange (584), so every npc inherited the dogma
    default of 100km as its leash and fought at the leash boundary, never closing.
  * 304 entity types carry the turret effect with no damage attributes, so they fire and do nothing.

Each was invisible until someone noticed the game felt wrong, then spent hours bisecting.  Each was also a
one-line query away.  This script is that collection of queries.

Checks are grouped by what they protect, and each prints its own count plus a sample.  A check that finds
nothing prints one PASS line.  The exit status is non-zero when any check at severity ERROR found something,
so this can gate a deploy.

Usage:
    ./check_data.py                                 # docker exec into evemu_db (the default)
    ./check_data.py --container db_spike            # a different container
    ./check_data.py --mysql "mariadb -uevemu -pevemu evemu"   # any client command
    ./check_data.py --only spawn,npc                # run a subset of groups
    ./check_data.py --sample 20                     # rows to show per finding
"""

import argparse
import subprocess
import sys

# ---------------------------------------------------------------------------
# Each check:  (group, name, severity, why it matters, query).
#
# A query returns the OFFENDING rows -- empty means healthy.  Keep the first column
# identifying (a typeID, a roomID) so the sample is useful on its own.
# ---------------------------------------------------------------------------

ERROR, WARN = "ERROR", "WARN"

CHECKS = [

    # -- npc combat data ----------------------------------------------------
    ("npc", "entity types with a turret effect but no damage", ERROR,
     "They fire every cycle and apply nothing.  NpcProfile disables the turret (TurretNoDamage), so the npc "
     "is a target dummy that looks armed.",
     """
     SELECT t.typeID, t.typeName, g.groupName
     FROM invTypes t JOIN invGroups g ON g.groupID = t.groupID
     JOIN dgmTypeEffects e ON e.typeID = t.typeID AND e.effectID = 10
     WHERE g.categoryID = 11
       AND NOT EXISTS (SELECT 1 FROM dgmTypeAttributes a
                       WHERE a.typeID = t.typeID AND a.attributeID IN (114,116,117,118)
                         AND COALESCE(a.valueFloat, a.valueInt) > 0)
     """),

    ("npc", "entity types with a missile effect but no missile type", ERROR,
     "effect 569 without entityMissileTypeID (507):  hasMissile is set and LaunchMissile has nothing to fire.",
     """
     SELECT t.typeID, t.typeName
     FROM invTypes t JOIN invGroups g ON g.groupID = t.groupID
     JOIN dgmTypeEffects e ON e.typeID = t.typeID AND e.effectID = 569
     WHERE g.categoryID = 11
       AND NOT EXISTS (SELECT 1 FROM dgmTypeAttributes a
                       WHERE a.typeID = t.typeID AND a.attributeID = 507
                         AND COALESCE(a.valueFloat, a.valueInt) > 0)
     """),

    ("npc", "armed entity types with no entityAttackRange", WARN,
     "attributeID 247 absent:  NpcProfile falls back to the dogma default for every one of them, so they all "
     "share a range the content never chose.",
     """
     SELECT t.typeID, t.typeName
     FROM invTypes t JOIN invGroups g ON g.groupID = t.groupID
     JOIN dgmTypeEffects e ON e.typeID = t.typeID AND e.effectID IN (10,569)
     WHERE g.categoryID = 11
       AND NOT EXISTS (SELECT 1 FROM dgmTypeAttributes a WHERE a.typeID = t.typeID AND a.attributeID = 247)
     GROUP BY t.typeID
     """),

    ("npc", "turret entity types with no trackingSpeed", WARN,
     "attributeID 160 absent:  NpcMath's track term divides by tracking, so these hit only targets with no "
     "angular velocity.  Flagged by NpcProfile as NoTracking.",
     """
     SELECT t.typeID, t.typeName
     FROM invTypes t JOIN invGroups g ON g.groupID = t.groupID
     JOIN dgmTypeEffects e ON e.typeID = t.typeID AND e.effectID = 10
     WHERE g.categoryID = 11
       AND NOT EXISTS (SELECT 1 FROM dgmTypeAttributes a WHERE a.typeID = t.typeID AND a.attributeID = 160)
     """),

    ("npc", "npc ai attributes with no rows at all", ERROR,
     "An attribute no type carries means every npc silently inherits its dogma default.  entityMaxWanderRange "
     "(584, default 100000) did this and gave every rat a 100km leash.",
     """
     SELECT at.attributeID, at.attributeName, at.defaultValue
     FROM dgmAttributeTypes at
     WHERE at.attributeID IN (247, 416, 508, 584, 665, 1416)
       AND NOT EXISTS (SELECT 1 FROM dgmTypeAttributes a WHERE a.attributeID = at.attributeID)
     """),

    # -- the missing-multiplier class --------------------------------------
    ("dogma", "types carrying part of a multiplier family", ERROR,
     "A module with some of the *Multiplier attributes but not all of them.  The effects processor reads a "
     "missing source attribute as 0 and a multiply becomes an erase -- this is exactly the Imperial Navy "
     "Capacitor Power Relay, which had 144/145/146/147 but not 134, and zeroed its ship's shield recharge.  "
     "The code now substitutes dogma's default, so these are no longer fatal, but each one is content that "
     "does not do what its siblings imply.",
     """
     SELECT t.typeID, t.typeName,
            GROUP_CONCAT(a.attributeID ORDER BY a.attributeID) AS has_multipliers
     FROM invTypes t JOIN dgmTypeAttributes a ON a.typeID = t.typeID
     WHERE a.attributeID IN (134,144,145,146,147)
     GROUP BY t.typeID
     HAVING COUNT(*) BETWEEN 2 AND 4
     """),

    # -- dungeon content ----------------------------------------------------
    ("spawn", "anomaly or unrated waves that spawn beyond 10km", WARN,
     "spread is the radius a wave lands in around the room origin.  Past ~10km the player must cross the site "
     "a group at a time, because an npc only closes to its own orbit range.  Missions are exempt:  their "
     "per-group offsets are deliberate pocket layouts.",
     """
     SELECT g.spawnGroupID, g.roomID, g.waveNumber, g.spread, d.archetypeID
     FROM dunSpawnGroups g JOIN dunRooms r ON r.roomID = g.roomID
     JOIN dunDungeons d ON d.dungeonID = r.dungeonID
     WHERE d.archetypeID IN (7,8) AND g.spread > 10000
     """),

    ("spawn", "spawn groups flagged warpIn", WARN,
     "warpIn makes SpawnDungeonNPC create the group 100-150km off its spot, and nothing warps it back in.  "
     "Until the GetBool fix every group read as true;  any that are genuinely set deserve a second look.",
     """
     SELECT g.spawnGroupID, g.roomID, g.waveNumber, d.archetypeID
     FROM dunSpawnGroups g JOIN dunRooms r ON r.roomID = g.roomID
     JOIN dunDungeons d ON d.dungeonID = r.dungeonID
     WHERE g.warpIn <> 0
     """),

    ("spawn", "combat sites with no decoration", WARN,
     "An archetype 7 or 8 room with no dunRoomObjects renders as empty space with ships floating in it.  150 "
     "of the 165 pirate anomaly rooms were like this until the F13 migration.",
     """
     SELECT r.roomID, d.dungeonID, d.archetypeID
     FROM dunRooms r JOIN dunDungeons d ON d.dungeonID = r.dungeonID
     WHERE d.archetypeID IN (7,8)
       AND NOT EXISTS (SELECT 1 FROM dunRoomObjects o WHERE o.roomID = r.roomID)
     """),

    ("spawn", "spawn groups whose room does not exist", ERROR,
     "The loader skips a group whose roomID is not in dunRooms, so the wave silently never spawns.",
     """
     SELECT g.spawnGroupID, g.roomID
     FROM dunSpawnGroups g
     WHERE NOT EXISTS (SELECT 1 FROM dunRooms r WHERE r.roomID = g.roomID)
     """),

    ("spawn", "room objects of a type the client cannot draw", ERROR,
     "A dunRoomObjects row whose typeID is not in invTypes.  The object is spawned and the client has nothing "
     "to render.",
     """
     SELECT o.objectID, o.roomID, o.typeID
     FROM dunRoomObjects o
     WHERE NOT EXISTS (SELECT 1 FROM invTypes t WHERE t.typeID = o.typeID)
     """),

    # -- referential integrity ---------------------------------------------
    ("refs", "dgmTypeAttributes rows for an unknown attribute", WARN,
     "Dead rows:  nothing reads them, and they make attribute coverage counts lie.",
     """
     SELECT DISTINCT a.attributeID
     FROM dgmTypeAttributes a
     WHERE NOT EXISTS (SELECT 1 FROM dgmAttributeTypes at WHERE at.attributeID = a.attributeID)
     """),

    ("refs", "dgmTypeEffects rows for an unknown effect", WARN,
     "An effect the engine has no definition for is skipped, so the type quietly lacks the behaviour its data "
     "promises.",
     """
     SELECT DISTINCT e.effectID
     FROM dgmTypeEffects e
     WHERE NOT EXISTS (SELECT 1 FROM dgmEffects ef WHERE ef.effectID = e.effectID)
     """),
]


def run_query(client, sql):
    """Run one query and return (header, rows).  Tab separated, no pager, no column box."""
    proc = subprocess.run(client + ["-B", "-e", sql], capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "query failed")
    lines = [ln for ln in proc.stdout.splitlines() if ln.strip()]
    if not lines:
        return [], []
    return lines[0].split("\t"), [ln.split("\t") for ln in lines[1:]]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--container", default="evemu_db", help="docker container running the database")
    ap.add_argument("--mysql", help="full client command, used instead of docker exec")
    ap.add_argument("--only", help="comma separated group names (npc, dogma, spawn, refs)")
    ap.add_argument("--sample", type=int, default=5, help="offending rows to print per check")
    args = ap.parse_args()

    if args.mysql:
        client = args.mysql.split()
    else:
        client = ["docker", "exec", args.container, "mariadb", "-uevemu", "-pevemu", "evemu"]

    wanted = set(args.only.split(",")) if args.only else None
    failures = warnings = 0

    for group, name, severity, why, sql in CHECKS:
        if wanted and group not in wanted:
            continue
        try:
            header, rows = run_query(client, sql)
        except RuntimeError as err:
            print(f"[SKIP ] {group:6} {name}\n         {err}")
            continue

        if not rows:
            print(f"[PASS ] {group:6} {name}")
            continue

        tag = "FAIL " if severity == ERROR else "WARN "
        if severity == ERROR:
            failures += 1
        else:
            warnings += 1
        print(f"[{tag}] {group:6} {name}:  {len(rows)}")
        print(f"         {why}")
        print(f"         {' | '.join(header)}")
        for row in rows[:args.sample]:
            print(f"           {' | '.join(row)}")
        if len(rows) > args.sample:
            print(f"           ... and {len(rows) - args.sample} more")

    print(f"\n{failures} error check(s) found something, {warnings} warning check(s).")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
