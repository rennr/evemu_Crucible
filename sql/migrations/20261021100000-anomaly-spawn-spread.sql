-- Anomaly and unrated spawn spread:  bring every wave inside 10km of the site beacon.
--
-- Why:  a spawn group places each npc at room.origin + MakeRandomPointOnSphere(U(0, spread)), so
--  `spread` is the radius of the shell a wave lands in.  The seed uses 15km for wave 1 and 20km for
--  every later wave, which scatters a site over a 40km diameter:  the player warps to 0 on the beacon
--  and then has to fly out to each group in turn, a few km at a time, because an npc only closes to
--  its own orbit range and a battleship cruises at 140 m/s.  Era behaviour is the whole first group
--  sitting 5-10km off the centre object you orbit.
--
-- What:  spread 10000 for archetypes 7 (combat anomaly) and 8 (unrated), so a wave lands uniformly in
--  [0, 10km] of the beacon -- mean ~5km, worst case 10km.  Archetype 1 (missions) is deliberately left
--  alone:  mission pockets carry real per-group x/y/z offsets (up to 155km) and are laid out that way
--  on purpose.  Archetype 8 wave 9 is already 10000 and is untouched by both directions.
--
-- Reversible:  Down restores 15000 for wave 1 and 20000 for waves 2-7, the seeded values.

-- +migrate Up
UPDATE `dunSpawnGroups` g
  JOIN `dunRooms` r ON r.roomID = g.roomID
  JOIN `dunDungeons` d ON d.dungeonID = r.dungeonID
SET g.spread = 10000
WHERE d.archetypeID IN (7, 8)
  AND g.spread > 10000;

-- +migrate Down
UPDATE `dunSpawnGroups` g
  JOIN `dunRooms` r ON r.roomID = g.roomID
  JOIN `dunDungeons` d ON d.dungeonID = r.dungeonID
SET g.spread = 15000
WHERE d.archetypeID IN (7, 8)
  AND g.waveNumber = 1
  AND g.spread = 10000;

UPDATE `dunSpawnGroups` g
  JOIN `dunRooms` r ON r.roomID = g.roomID
  JOIN `dunDungeons` d ON d.dungeonID = r.dungeonID
SET g.spread = 20000
WHERE d.archetypeID IN (7, 8)
  AND g.waveNumber BETWEEN 2 AND 7
  AND g.spread = 10000;
