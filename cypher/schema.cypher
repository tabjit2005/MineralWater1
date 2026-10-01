CREATE CONSTRAINT customer_id_unique IF NOT EXISTS
FOR (u:Customer) REQUIRE u.customer_id IS UNIQUE;

CREATE CONSTRAINT water_id_unique IF NOT EXISTS
FOR (w:Water) REQUIRE w.water_id IS UNIQUE;
