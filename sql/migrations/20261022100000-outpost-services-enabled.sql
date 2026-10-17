-- Outpost service entities online.
--
-- Why:  StationDB::GetStationServiceStates reports a station service enabled when its entity (the
--  Destructable Station Services types 28155-28166 at the outpost's position) has flag 144,
--  flagStructureActive, and the client's lobby shows every other one as 'Disabled'.  The server spawned
--  them with flag 0, so a built outpost's fitting, reprocessing, factory, cloning, repair and laboratory
--  services all showed as disabled although they worked.  New ones are spawned active;  this fixes the
--  ones already built.
--
-- Idempotent:  only flag 0 rows of those types change.  Down puts them back to 0.

-- +migrate Up
UPDATE `entity`
SET flag = 144
WHERE typeID IN (28155, 28156, 28157, 28158, 28159, 28166)
  AND flag = 0;

-- +migrate Down
UPDATE `entity`
SET flag = 0
WHERE typeID IN (28155, 28156, 28157, 28158, 28159, 28166)
  AND flag = 144;
