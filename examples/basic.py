from splash_links.client.base import from_uri

links = from_uri("splash://localhost:8080")

entity = links.create_entity(entity_type="Person", properties={"name": "Alice"})
print(f"Created entity: {entity.id} of type {entity.entity_type}")

entity2 = links.create_entity(entity_type="Person", properties={"name": "Bob"})

link = links.create_link(
    subject_id=entity,
    predicate="knows",
    object_id=entity2,
)

print(f"Created link: {link.id} ({link.subject_id} {link.predicate} {link.object_id})")


# Now do tiled client
from tiled.client import from_uri as tiled_from_uri
tiled_client = tiled_from_uri("http://localhost:8000")

raw = tiled_client['/raw/raw1']
processed1 = tiled_client['/processed/processed1']
processed2 = tiled_client['/processed/processed2']
extra_processed = tiled_client['/processed/custom/extra_processed1']

# create_link detects that items are tiled objects and creates entities if not already existing
# and also creates the link between them
raw_to_processed1= links.create_link(processed1, "processed_from", raw)
processed1_to_extra = links.create_link(extra_processed, "custom_processed_from", processed1)
extra_processed_to_processed2 = links.create_link(processed2, "processed_from", extra_processed)


# find all of processed1 links
processed1_links = links.find_links(processed1)  # find all links involving processed1
assert len(processed1_links) == 2  # should have two links

# find all direct prcocessed items from raw
processed_from_raw = links.find_links(raw, predicate="processed_from")  # find links with specific predicate
assert len(processed_from_raw) == 2






