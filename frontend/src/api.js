const GQL_URL = '/splash_links/graphql';

async function gql(query, variables = {}) {
  const res = await fetch(GQL_URL, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, variables }),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`);
  const body = await res.json();
  if (body.errors) throw new Error(body.errors.map((e) => e.message).join('\n'));
  return body.data;
}

const ENTITY_FIELDS = 'id entityType name uri createdAt';
const LINK_FIELDS = 'id subjectId predicate objectId';

export const getGraph = () =>
  gql(`query {
    entities(limit: 500) { ${ENTITY_FIELDS} }
    links(limit: 500) { ${LINK_FIELDS} }
  }`);

export const createProject = (name) =>
  gql(
    `mutation CreateProject($name: String!) {
      createEntity(input: { entityType: "project", name: $name }) { ${ENTITY_FIELDS} }
    }`,
    { name },
  );

export const createEntity = (entityType, name, uri) =>
  gql(
    `mutation CreateEntity($entityType: String!, $name: String!, $uri: String) {
      createEntity(input: { entityType: $entityType, name: $name, uri: $uri }) { ${ENTITY_FIELDS} }
    }`,
    { entityType, name, uri: uri || null },
  );

export const createLink = (subjectId, predicate, objectId) =>
  gql(
    `mutation CreateLink($subjectId: ID!, $predicate: String!, $objectId: ID!) {
      createLink(input: { subjectId: $subjectId, predicate: $predicate, objectId: $objectId }) { ${LINK_FIELDS} }
    }`,
    { subjectId, predicate, objectId },
  );

export const deleteLink = (id) =>
  gql(`mutation($id: ID!) { deleteLink(id: $id) }`, { id });

export const updateLink = (id, predicate) =>
  gql(
    `mutation UpdateLink($id: ID!, $predicate: String!) {
      updateLink(id: $id, input: { predicate: $predicate }) { ${LINK_FIELDS} }
    }`,
    { id, predicate },
  );

export const deleteEntity = (id) =>
  gql(`mutation($id: ID!) { deleteEntity(id: $id) }`, { id });

export const updateEntity = (id, { name, uri, entityType }) =>
  gql(
    `mutation UpdateEntity($id: ID!, $name: String, $uri: String, $entityType: String) {
      updateEntity(id: $id, input: { name: $name, uri: $uri, entityType: $entityType }) { ${ENTITY_FIELDS} }
    }`,
    { id, name: name ?? null, uri: uri ?? null, entityType: entityType ?? null },
  );
