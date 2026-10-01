from __future__ import annotations

from typing import Any

import streamlit as st
from neo4j import GraphDatabase, RoutingControl


def _config() -> tuple[str, str, str, str]:
    cfg = st.secrets["neo4j"]
    return (
        cfg["uri"],
        cfg["username"],
        cfg["password"],
        cfg.get("database", "12ca74ed"),
    )


@st.cache_resource(show_spinner=False)
def get_driver():
    """Create one thread-safe Neo4j Driver for the Streamlit process."""
    uri, username, password, _ = _config()
    driver = GraphDatabase.driver(uri, auth=(username, password))
    driver.verify_connectivity()
    return driver


def query(cypher: str, parameters: dict[str, Any] | None = None, *, write: bool = False) -> list[dict[str, Any]]:
    """Execute parameterized Cypher and return rows as dictionaries."""
    _, _, _, database = _config()
    records, _, _ = get_driver().execute_query(
        cypher,
        parameters_=parameters or {},
        database_=database,
        routing_=RoutingControl.WRITE if write else RoutingControl.READ,
    )
    return [record.data() for record in records]


def ping() -> bool:
    rows = query("RETURN 1 AS ok")
    return bool(rows and rows[0]["ok"] == 1)


def create_schema() -> None:
    statements = [
        "CREATE CONSTRAINT customer_id_unique IF NOT EXISTS FOR (u:Customer) REQUIRE u.customer_id IS UNIQUE",
        "CREATE CONSTRAINT water_id_unique IF NOT EXISTS FOR (w:Water) REQUIRE w.water_id IS UNIQUE",
    ]
    for stmt in statements:
        query(stmt, write=True)


def seed_demo_data() -> None:
    """Idempotent sample dataset from the course notebook: safe to run more than once."""
    create_schema()

    customers = [
        {"customer_id": "C001", "name": "Kanya"},
        {"customer_id": "C002", "name": "Nattapong"},
        {"customer_id": "C003", "name": "Siriporn"},
        {"customer_id": "C004", "name": "Thanakrit"},
        {"customer_id": "C005", "name": "Preecha"},
        {"customer_id": "C006", "name": "Malee"},
        {"customer_id": "C007", "name": "Chaiyut"},
        {"customer_id": "C008", "name": "Nichada"},
        {"customer_id": "C009", "name": "Somsak"},
        {"customer_id": "C010", "name": "Ratree"},
    ]
    waters = [
        {"water_id": "W101", "name": "Singha"},
        {"water_id": "W102", "name": "Crystal"},
        {"water_id": "W103", "name": "Minere"},
        {"water_id": "W104", "name": "Nestle Pure Life"},
        {"water_id": "W105", "name": "Perrier"},
        {"water_id": "W106", "name": "Namthip"},
        {"water_id": "W107", "name": "evian"},
    ]
    query(
        """
        UNWIND $rows AS row
        MERGE (u:Customer {customer_id: row.customer_id})
        SET u.name = row.name
        """,
        {"rows": customers},
        write=True,
    )
    query(
        """
        UNWIND $rows AS row
        MERGE (w:Water {water_id: row.water_id})
        SET w.name = row.name
        """,
        {"rows": waters},
        write=True,
    )

    similarities = [
        ["C001", "C002"], ["C001", "C005"], ["C001", "C008"], ["C002", "C008"],
        ["C002", "C009"], ["C003", "C007"], ["C003", "C010"], ["C004", "C009"],
        ["C005", "C006"], ["C006", "C009"], ["C007", "C010"], ["C004", "C005"],
    ]
    # Undirected MERGE: one SIMILAR_TO per pair, whichever direction already exists.
    query(
        """
        UNWIND $rows AS row
        MATCH (a:Customer {customer_id: row[0]}), (b:Customer {customer_id: row[1]})
        MERGE (a)-[:SIMILAR_TO]-(b)
        """,
        {"rows": similarities},
        write=True,
    )

    likes = [
        ["C001", "W101"], ["C001", "W102"],
        ["C002", "W101"], ["C002", "W102"], ["C002", "W104"],
        ["C003", "W101"], ["C003", "W103"],
        ["C004", "W104"], ["C004", "W105"],
        ["C005", "W102"], ["C005", "W106"],
        ["C006", "W101"], ["C006", "W106"], ["C006", "W107"],
        ["C007", "W103"], ["C007", "W105"],
        ["C008", "W101"], ["C008", "W102"], ["C008", "W107"],
        ["C009", "W104"], ["C009", "W106"],
        ["C010", "W103"], ["C010", "W105"], ["C010", "W107"],
    ]
    query(
        """
        UNWIND $rows AS row
        MATCH (u:Customer {customer_id: row[0]}), (w:Water {water_id: row[1]})
        MERGE (u)-[:LIKES]->(w)
        """,
        {"rows": likes},
        write=True,
    )


# ---------- Customer ----------

def get_customers() -> list[dict[str, Any]]:
    return query(
        """
        MATCH (u:Customer)
        OPTIONAL MATCH (u)-[:LIKES]->(w:Water)
        WITH u, count(DISTINCT w) AS likes
        OPTIONAL MATCH (u)-[:SIMILAR_TO]-(o:Customer)
        RETURN u.customer_id AS customer_id, u.name AS name,
               likes, count(DISTINCT o) AS similar
        ORDER BY customer_id
        """
    )


def create_customer(customer_id: str, name: str) -> bool:
    """Return False when the customer_id is already taken."""
    rows = query(
        """
        OPTIONAL MATCH (x:Customer {customer_id:$customer_id})
        WITH x WHERE x IS NULL
        CREATE (u:Customer {customer_id:$customer_id, name:$name})
        RETURN u.customer_id AS customer_id
        """,
        {"customer_id": customer_id, "name": name},
        write=True,
    )
    return bool(rows)


def update_customer(customer_id: str, name: str) -> bool:
    rows = query(
        """
        MATCH (u:Customer {customer_id:$customer_id})
        SET u.name = $name
        RETURN u.customer_id AS customer_id
        """,
        {"customer_id": customer_id, "name": name},
        write=True,
    )
    return bool(rows)


def delete_customer(customer_id: str) -> bool:
    """DETACH DELETE: also removes the customer's LIKES and SIMILAR_TO relationships."""
    rows = query(
        """
        MATCH (u:Customer {customer_id:$customer_id})
        DETACH DELETE u
        RETURN count(*) AS deleted
        """,
        {"customer_id": customer_id},
        write=True,
    )
    return bool(rows and rows[0]["deleted"])


# ---------- Water ----------

def get_waters() -> list[dict[str, Any]]:
    return query(
        """
        MATCH (w:Water)
        OPTIONAL MATCH (u:Customer)-[:LIKES]->(w)
        RETURN w.water_id AS water_id, w.name AS name, count(DISTINCT u) AS likes
        ORDER BY water_id
        """
    )


def create_water(water_id: str, name: str) -> bool:
    """Return False when the water_id is already taken."""
    rows = query(
        """
        OPTIONAL MATCH (x:Water {water_id:$water_id})
        WITH x WHERE x IS NULL
        CREATE (w:Water {water_id:$water_id, name:$name})
        RETURN w.water_id AS water_id
        """,
        {"water_id": water_id, "name": name},
        write=True,
    )
    return bool(rows)


def update_water(water_id: str, name: str) -> bool:
    rows = query(
        """
        MATCH (w:Water {water_id:$water_id})
        SET w.name = $name
        RETURN w.water_id AS water_id
        """,
        {"water_id": water_id, "name": name},
        write=True,
    )
    return bool(rows)


def get_water_images() -> dict[str, bytes]:
    """Uploaded pictures keyed by water_id; waters without one are absent."""
    rows = query(
        """
        MATCH (w:Water)
        WHERE w.image IS NOT NULL
        RETURN w.water_id AS water_id, w.image AS image
        """
    )
    return {row["water_id"]: bytes(row["image"]) for row in rows}


def set_water_image(water_id: str, image: bytes | None) -> bool:
    """Store the picture as a byte-array property; None removes it (SET to null drops the property)."""
    rows = query(
        """
        MATCH (w:Water {water_id:$water_id})
        SET w.image = $image
        RETURN w.water_id AS water_id
        """,
        {"water_id": water_id, "image": image},
        write=True,
    )
    return bool(rows)


def delete_water(water_id: str) -> bool:
    """DETACH DELETE: also removes every LIKES relationship pointing at the water."""
    rows = query(
        """
        MATCH (w:Water {water_id:$water_id})
        DETACH DELETE w
        RETURN count(*) AS deleted
        """,
        {"water_id": water_id},
        write=True,
    )
    return bool(rows and rows[0]["deleted"])


# ---------- Relationships ----------

def list_likes() -> list[dict[str, Any]]:
    return query(
        """
        MATCH (u:Customer)-[:LIKES]->(w:Water)
        RETURN u.customer_id AS customer_id, u.name AS customer,
               w.water_id AS water_id, w.name AS water
        ORDER BY customer_id, water_id
        """
    )


def set_likes(customer_id: str, water_ids: list[str]) -> None:
    """Make the customer's LIKES exactly `water_ids`: drop the rest, add the missing."""
    params = {"customer_id": customer_id, "water_ids": water_ids}
    query(
        """
        MATCH (u:Customer {customer_id:$customer_id})-[r:LIKES]->(w:Water)
        WHERE NOT w.water_id IN $water_ids
        DELETE r
        """,
        params,
        write=True,
    )
    query(
        """
        MATCH (u:Customer {customer_id:$customer_id})
        UNWIND $water_ids AS water_id
        MATCH (w:Water {water_id: water_id})
        MERGE (u)-[:LIKES]->(w)
        """,
        params,
        write=True,
    )


def list_similarities() -> list[dict[str, Any]]:
    return query(
        """
        MATCH (a:Customer)-[:SIMILAR_TO]->(b:Customer)
        RETURN a.customer_id AS customer1_id, a.name AS customer1,
               b.customer_id AS customer2_id, b.name AS customer2
        ORDER BY customer1_id, customer2_id
        """
    )


def set_similar(customer_id: str, other_ids: list[str]) -> None:
    """Make the customer's SIMILAR_TO neighbours exactly `other_ids` (either direction)."""
    params = {"customer_id": customer_id, "other_ids": other_ids}
    query(
        """
        MATCH (a:Customer {customer_id:$customer_id})-[r:SIMILAR_TO]-(b:Customer)
        WHERE NOT b.customer_id IN $other_ids
        DELETE r
        """,
        params,
        write=True,
    )
    query(
        """
        MATCH (a:Customer {customer_id:$customer_id})
        UNWIND $other_ids AS other_id
        MATCH (b:Customer {customer_id: other_id})
        WHERE a <> b
        MERGE (a)-[:SIMILAR_TO]-(b)
        """,
        params,
        write=True,
    )


# ---------- Read models ----------

def get_dashboard_metrics() -> dict[str, int]:
    rows = query(
        """
        OPTIONAL MATCH (u:Customer) WITH count(u) AS customers
        OPTIONAL MATCH (w:Water) WITH customers, count(w) AS waters
        OPTIONAL MATCH (:Customer)-[l:LIKES]->(:Water) WITH customers, waters, count(l) AS likes
        OPTIONAL MATCH (:Customer)-[s:SIMILAR_TO]->(:Customer)
        RETURN customers, waters, likes, count(s) AS similarities
        """
    )
    return rows[0] if rows else {"customers": 0, "waters": 0, "likes": 0, "similarities": 0}


def get_profile(customer_id: str) -> dict[str, Any] | None:
    rows = query(
        """
        MATCH (u:Customer {customer_id:$customer_id})
        OPTIONAL MATCH (u)-[:LIKES]->(w:Water)
        WITH u, collect(DISTINCT {water_id: w.water_id, name: w.name}) AS liked
        OPTIONAL MATCH (u)-[:SIMILAR_TO]-(o:Customer)
        RETURN u.customer_id AS customer_id, u.name AS name, liked,
               collect(DISTINCT {customer_id: o.customer_id, name: o.name}) AS similar
        """,
        {"customer_id": customer_id},
    )
    if not rows:
        return None
    row = rows[0]
    # OPTIONAL MATCH yields one all-null map when there is no match; drop it and fix column order.
    row["liked"] = sorted(
        ({"water_id": x["water_id"], "name": x["name"]} for x in row["liked"] if x.get("water_id")),
        key=lambda x: x["water_id"],
    )
    row["similar"] = sorted(
        ({"customer_id": x["customer_id"], "name": x["name"]} for x in row["similar"] if x.get("customer_id")),
        key=lambda x: x["customer_id"],
    )
    return row


def recommend_waters(customer_id: str, limit: int = 8) -> list[dict[str, Any]]:
    """Waters liked by similar customers that the customer does not like yet.

    score = number of similar customers who like the water.
    """
    return query(
        """
        MATCH (me:Customer {customer_id:$customer_id})
              -[:SIMILAR_TO]-(similar:Customer)
              -[:LIKES]->(water:Water)
        WHERE NOT EXISTS { MATCH (me)-[:LIKES]->(water) }
        WITH DISTINCT water, similar
        ORDER BY similar.customer_id
        RETURN water.water_id AS water_id, water.name AS recommendation,
               count(similar) AS score,
               collect(similar.name) AS similar_names
        ORDER BY score DESC, recommendation
        LIMIT $limit
        """,
        {"customer_id": customer_id, "limit": int(limit)},
    )


def graph_neighborhood(customer_id: str, limit: int = 60) -> list[dict[str, Any]]:
    return query(
        """
        MATCH (u:Customer {customer_id:$customer_id})
        OPTIONAL MATCH p=(u)-[:SIMILAR_TO|LIKES*1..2]-(x)
        WITH u, collect(p)[0..$limit] AS paths
        UNWIND paths AS p
        UNWIND relationships(p) AS r
        WITH DISTINCT startNode(r) AS s, r, endNode(r) AS t
        RETURN coalesce(s.customer_id, s.water_id) AS source_id, labels(s)[0] AS source_label,
               s.name AS source_name,
               type(r) AS relationship,
               coalesce(t.customer_id, t.water_id) AS target_id, labels(t)[0] AS target_label,
               t.name AS target_name
        """,
        {"customer_id": customer_id, "limit": int(limit)},
    )
