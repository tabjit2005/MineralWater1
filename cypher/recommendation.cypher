// Mineral Water Recommendation
// Parameters: $customer_id, $limit
// Waters liked by similar customers that the customer does not like yet.
// SIMILAR_TO is matched without direction, so similarity is symmetric.
MATCH (me:Customer {customer_id:$customer_id})
      -[:SIMILAR_TO]-(similar:Customer)
      -[:LIKES]->(water:Water)
WHERE NOT EXISTS { MATCH (me)-[:LIKES]->(water) }
WITH DISTINCT water, similar
ORDER BY similar.customer_id

// score = number of similar customers who like the water
RETURN water.water_id AS water_id,
       water.name AS recommendation,
       count(similar) AS score,
       collect(similar.name) AS similar_names
ORDER BY score DESC, recommendation
LIMIT $limit;
