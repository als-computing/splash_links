import { useState, useMemo } from 'react';
import * as api from '../api.js';

const PRESET_PREDICATES = ['contains', 'references', 'derived_from', 'produced', 'includes'];
const PRESET_TYPES = ['project', 'tiled'];

const TYPE_COLORS = {
  project: '#0ea5e9',
  tiled: '#f97316',
};

function dot(type) {
  const color = TYPE_COLORS[type] ?? '#6b7280';
  return (
    <span
      style={{
        display: 'inline-block',
        width: 10,
        height: 10,
        borderRadius: '50%',
        background: color,
        marginRight: 6,
        flexShrink: 0,
      }}
    />
  );
}

function EntityRow({ entity, isSubject, isObject, onSetSubject, onSetObject, onRefresh, onError }) {
  const [editing, setEditing] = useState(false);
  const [editName, setEditName] = useState(entity.name);
  const [editUri, setEditUri] = useState(entity.uri ?? '');
  const [editType, setEditType] = useState(entity.entityType);
  const [saving, setSaving] = useState(false);

  const startEdit = () => {
    setEditName(entity.name);
    setEditUri(entity.uri ?? '');
    setEditType(entity.entityType);
    setEditing(true);
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await api.updateEntity(entity.id, {
        name: editName.trim() || undefined,
        uri: editUri.trim() || undefined,
        entityType: editType.trim() || undefined,
      });
      setEditing(false);
      await onRefresh();
    } catch (err) {
      onError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!confirm(`Delete "${entity.name}" and all its links?`)) return;
    try {
      await api.deleteEntity(entity.id);
      await onRefresh();
    } catch (err) {
      onError(err.message);
    }
  };

  const rowBg = isSubject ? '#e0f2fe' : isObject ? '#fff7ed' : undefined;

  if (editing) {
    return (
      <tr style={{ borderBottom: '1px solid #f3f4f6', background: '#fffbeb' }}>
        <td style={{ padding: '4px 6px' }}>
          <input
            className="sl-input"
            style={{ fontSize: 12, padding: '2px 6px' }}
            value={editName}
            onChange={(e) => setEditName(e.target.value)}
          />
        </td>
        <td style={{ padding: '4px 6px' }}>
          <input
            className="sl-input"
            style={{ fontSize: 12, padding: '2px 6px', width: 90 }}
            value={editType}
            onChange={(e) => setEditType(e.target.value)}
          />
        </td>
        <td style={{ padding: '4px 6px' }}>
          <input
            className="sl-input"
            style={{ fontSize: 12, padding: '2px 6px' }}
            value={editUri}
            onChange={(e) => setEditUri(e.target.value)}
            placeholder="URI"
          />
        </td>
        <td colSpan={2} style={{ padding: '4px 6px' }}>
          <div style={{ display: 'flex', gap: 6 }}>
            <button className="sl-btn" style={{ fontSize: 11, padding: '2px 8px' }} onClick={handleSave} disabled={saving}>
              {saving ? '…' : 'Save'}
            </button>
            <button className="sl-btn sl-btn--outline" style={{ fontSize: 11, padding: '2px 8px' }} onClick={() => setEditing(false)}>
              Cancel
            </button>
          </div>
        </td>
      </tr>
    );
  }

  return (
    <tr style={{ borderBottom: '1px solid #f3f4f6', background: rowBg }}>
      <td style={{ padding: '5px 8px' }}>
        <div style={{ display: 'flex', alignItems: 'center' }}>
          {dot(entity.entityType)}
          <span style={{ fontWeight: 500 }}>{entity.name}</span>
        </div>
      </td>
      <td style={{ padding: '5px 8px', color: '#6b7280' }}>{entity.entityType}</td>
      <td
        style={{ padding: '5px 8px', color: '#6b7280', maxWidth: 180, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
        title={entity.uri ?? ''}
      >
        {entity.uri ?? '—'}
      </td>
      <td style={{ padding: '5px 6px' }}>
        <button
          className={`sl-btn${isSubject ? '' : ' sl-btn--outline'}`}
          style={{ fontSize: 11, padding: '2px 8px' }}
          onClick={() => onSetSubject(isSubject ? '' : entity.id)}
        >
          {isSubject ? '✓ Subj' : '→ Subj'}
        </button>
      </td>
      <td style={{ padding: '5px 6px' }}>
        <button
          className={`sl-btn${isObject ? '' : ' sl-btn--outline'}`}
          style={{ fontSize: 11, padding: '2px 8px' }}
          onClick={() => onSetObject(isObject ? '' : entity.id)}
          disabled={isSubject}
        >
          {isObject ? '✓ Obj' : '→ Obj'}
        </button>
      </td>
      <td style={{ padding: '5px 6px' }}>
        <div style={{ display: 'flex', gap: 4 }}>
          <button className="sl-btn sl-btn--outline" style={{ fontSize: 11, padding: '2px 7px' }} onClick={startEdit} title="Edit">✎</button>
          <button className="sl-del-btn" onClick={handleDelete} title="Delete entity">×</button>
        </div>
      </td>
    </tr>
  );
}

function LinkRow({ link, entities, onRefresh, onError }) {
  const [editing, setEditing] = useState(false);
  const [editPred, setEditPred] = useState(link.predicate);
  const [useCustom, setUseCustom] = useState(!PRESET_PREDICATES.includes(link.predicate));
  const [saving, setSaving] = useState(false);

  const subj = entities.find((e) => e.id === link.subjectId);
  const obj = entities.find((e) => e.id === link.objectId);

  const handleSave = async () => {
    const pred = editPred.trim();
    if (!pred) return;
    setSaving(true);
    try {
      await api.updateLink(link.id, pred);
      setEditing(false);
      await onRefresh();
    } catch (err) {
      onError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    try {
      await api.deleteLink(link.id);
      await onRefresh();
    } catch (err) {
      onError(err.message);
    }
  };

  if (editing) {
    return (
      <li style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '5px 0', borderBottom: '1px solid #f3f4f6', flexWrap: 'wrap' }}>
        <span style={{ display: 'flex', alignItems: 'center' }}>{dot(subj?.entityType)}<strong>{subj?.name ?? link.subjectId}</strong></span>
        <select
          className="sl-input"
          style={{ width: 'auto', fontSize: 12 }}
          value={useCustom ? '__custom__' : editPred}
          onChange={(e) => {
            if (e.target.value === '__custom__') { setUseCustom(true); }
            else { setUseCustom(false); setEditPred(e.target.value); }
          }}
        >
          {PRESET_PREDICATES.map((p) => <option key={p} value={p}>{p}</option>)}
          <option value="__custom__">custom…</option>
        </select>
        {useCustom && (
          <input className="sl-input" style={{ width: 110, fontSize: 12 }} value={editPred} onChange={(e) => setEditPred(e.target.value)} />
        )}
        <span style={{ display: 'flex', alignItems: 'center' }}>{dot(obj?.entityType)}<strong>{obj?.name ?? link.objectId}</strong></span>
        <button className="sl-btn" style={{ fontSize: 11, padding: '2px 8px' }} onClick={handleSave} disabled={saving}>{saving ? '…' : 'Save'}</button>
        <button className="sl-btn sl-btn--outline" style={{ fontSize: 11, padding: '2px 8px' }} onClick={() => setEditing(false)}>Cancel</button>
      </li>
    );
  }

  return (
    <li className="sl-link-item">
      <span className="sl-link-text" style={{ display: 'flex', alignItems: 'center' }}>
        {dot(subj?.entityType)}<strong>{subj?.name ?? link.subjectId}</strong>
        <em style={{ margin: '0 6px', color: '#6b7280' }}>{link.predicate}</em>
        {dot(obj?.entityType)}<strong>{obj?.name ?? link.objectId}</strong>
      </span>
      <div style={{ display: 'flex', gap: 4, marginLeft: 'auto' }}>
        <button className="sl-btn sl-btn--outline" style={{ fontSize: 11, padding: '2px 7px' }} onClick={() => { setEditPred(link.predicate); setUseCustom(!PRESET_PREDICATES.includes(link.predicate)); setEditing(true); }} title="Edit">✎</button>
        <button className="sl-del-btn" onClick={handleDelete} title="Delete link">×</button>
      </div>
    </li>
  );
}

export default function EntityLinker({ entities, links, error, loading, onError, onRefresh }) {
  const [typeFilter, setTypeFilter] = useState('all');
  const [sortBy, setSortBy] = useState('name');

  const [subjectId, setSubjectId] = useState('');
  const [objectId, setObjectId] = useState('');
  const [predicate, setPredicate] = useState('contains');
  const [customPredicate, setCustomPredicate] = useState('');
  const [creating, setCreating] = useState(false);

  const [newType, setNewType] = useState('project');
  const [customType, setCustomType] = useState('');
  const [newName, setNewName] = useState('');
  const [newUri, setNewUri] = useState('');
  const [creatingEntity, setCreatingEntity] = useState(false);

  // Unique entity types for the filter dropdown
  const entityTypes = useMemo(
    () => ['all', ...Array.from(new Set(entities.map((e) => e.entityType))).sort()],
    [entities],
  );

  const filtered = useMemo(() => {
    let list = typeFilter === 'all' ? entities : entities.filter((e) => e.entityType === typeFilter);
    list = [...list].sort((a, b) => {
      if (sortBy === 'type') {
        const t = a.entityType.localeCompare(b.entityType);
        return t !== 0 ? t : a.name.localeCompare(b.name);
      }
      return a.name.localeCompare(b.name);
    });
    return list;
  }, [entities, typeFilter, sortBy]);

  const subject = entities.find((e) => e.id === subjectId);
  const object = entities.find((e) => e.id === objectId);
  const effectivePredicate = predicate === '__custom__' ? customPredicate.trim() : predicate;
  const canCreate = subjectId && objectId && subjectId !== objectId && effectivePredicate;

  const handleCreate = async (e) => {
    e.preventDefault();
    if (!canCreate) return;
    setCreating(true);
    try {
      await api.createLink(subjectId, effectivePredicate, objectId);
      setSubjectId('');
      setObjectId('');
      await onRefresh();
    } catch (err) {
      onError(err.message);
    } finally {
      setCreating(false);
    }
  };

  const handleCreateEntity = async (e) => {
    e.preventDefault();
    const resolvedType = newType === '__custom__' ? customType.trim() : newType;
    if (!newName.trim() || !resolvedType) return;
    setCreatingEntity(true);
    try {
      await api.createEntity(resolvedType, newName.trim(), newUri.trim() || undefined);
      setNewName('');
      setNewUri('');
      await onRefresh();
    } catch (err) {
      onError(err.message);
    } finally {
      setCreatingEntity(false);
    }
  };

  return (
    <div className="sl-page">
      {error && (
        <div className="sl-error-banner" onClick={() => onError(null)}>
          {error} <span>×</span>
        </div>
      )}

      <div className="sl-panels" style={{ flexDirection: 'column', gap: 24 }}>

        {/* ── Create entity ── */}
        <section className="sl-panel">
          <h2 className="sl-panel-title">Create Entity</h2>
          <form onSubmit={handleCreateEntity}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
              <select
                className="sl-input"
                style={{ width: 120 }}
                value={newType}
                onChange={(e) => { setNewType(e.target.value); setCustomType(''); }}
              >
                {Array.from(new Set([...PRESET_TYPES, ...entities.map((e) => e.entityType)])).map((t) => (
                  <option key={t} value={t}>{t}</option>
                ))}
                <option value="__custom__">Other…</option>
              </select>
              {newType === '__custom__' && (
                <input
                  className="sl-input"
                  style={{ width: 110 }}
                  value={customType}
                  onChange={(e) => setCustomType(e.target.value)}
                  placeholder="Custom type"
                  autoFocus
                />
              )}
              <input
                className="sl-input"
                style={{ flex: 1, minWidth: 120 }}
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                placeholder="Name"
              />
              <input
                className="sl-input"
                style={{ flex: 2, minWidth: 160 }}
                value={newUri}
                onChange={(e) => setNewUri(e.target.value)}
                placeholder="URI (optional)"
              />
              <button
                className="sl-btn"
                type="submit"
                disabled={creatingEntity || !newName.trim() || (newType === '__custom__' ? !customType.trim() : !newType)}
              >
                {creatingEntity ? '…' : '+ Create'}
              </button>
            </div>
          </form>
        </section>

        {/* ── Controls + Entity list ── */}
        <section className="sl-panel sl-panel--grow">
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 12, flexWrap: 'wrap' }}>
            <h2 className="sl-panel-title" style={{ margin: 0 }}>Entities</h2>
            <label className="sl-label" style={{ margin: 0, flexDirection: 'row', alignItems: 'center', gap: 6 }}>
              Type:
              <select className="sl-input" style={{ width: 'auto' }} value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)}>
                {entityTypes.map((t) => (
                  <option key={t} value={t}>{t === 'all' ? 'All types' : t}</option>
                ))}
              </select>
            </label>
            <label className="sl-label" style={{ margin: 0, flexDirection: 'row', alignItems: 'center', gap: 6 }}>
              Sort:
              <select className="sl-input" style={{ width: 'auto' }} value={sortBy} onChange={(e) => setSortBy(e.target.value)}>
                <option value="name">Name</option>
                <option value="type">Type</option>
              </select>
            </label>
            {(subjectId || objectId) && (
              <button
                className="sl-del-btn"
                style={{ marginLeft: 'auto' }}
                onClick={() => { setSubjectId(''); setObjectId(''); }}
                title="Clear selection"
              >
                Clear selection
              </button>
            )}
          </div>

          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr style={{ borderBottom: '1px solid #e5e7eb', textAlign: 'left' }}>
                <th style={{ padding: '4px 8px', color: '#6b7280', fontWeight: 500 }}>Name</th>
                <th style={{ padding: '4px 8px', color: '#6b7280', fontWeight: 500 }}>Type</th>
                <th style={{ padding: '4px 8px', color: '#6b7280', fontWeight: 500, whiteSpace: 'nowrap' }}>URI</th>
                <th style={{ padding: '4px 8px', color: '#6b7280', fontWeight: 500 }}>Subject</th>
                <th style={{ padding: '4px 8px', color: '#6b7280', fontWeight: 500 }}>Object</th>
                <th style={{ padding: '4px 8px', color: '#6b7280', fontWeight: 500 }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((e) => (
                <EntityRow
                  key={e.id}
                  entity={e}
                  isSubject={subjectId === e.id}
                  isObject={objectId === e.id}
                  onSetSubject={setSubjectId}
                  onSetObject={setObjectId}
                  onRefresh={onRefresh}
                  onError={onError}
                />
              ))}
              {filtered.length === 0 && !loading && (
                <tr>
                  <td colSpan={6} style={{ padding: '16px 8px', color: '#9ca3af', textAlign: 'center' }}>
                    No entities found
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </section>

        {/* ── Create link ── */}
        <section className="sl-panel">
          <h2 className="sl-panel-title">Create Link</h2>
          <form onSubmit={handleCreate}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap', marginBottom: 10 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '6px 10px', background: subjectId ? '#e0f2fe' : '#f3f4f6', borderRadius: 6, minWidth: 120 }}>
                {subjectId ? <>{dot(subject?.entityType)}<strong>{subject?.name}</strong></> : <span style={{ color: '#9ca3af' }}>Subject—</span>}
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <span style={{ color: '#9ca3af' }}>—</span>
                <select
                  className="sl-input"
                  style={{ width: 'auto' }}
                  value={predicate}
                  onChange={(e) => setPredicate(e.target.value)}
                >
                  {PRESET_PREDICATES.map((p) => (
                    <option key={p} value={p}>{p}</option>
                  ))}
                  <option value="__custom__">custom…</option>
                </select>
                {predicate === '__custom__' && (
                  <input
                    className="sl-input"
                    style={{ width: 120 }}
                    value={customPredicate}
                    onChange={(e) => setCustomPredicate(e.target.value)}
                    placeholder="predicate"
                  />
                )}
                <span style={{ color: '#9ca3af' }}>→</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '6px 10px', background: objectId ? '#fff7ed' : '#f3f4f6', borderRadius: 6, minWidth: 120 }}>
                {objectId ? <>{dot(object?.entityType)}<strong>{object?.name}</strong></> : <span style={{ color: '#9ca3af' }}>—Object</span>}
              </div>
              <button className="sl-btn" type="submit" disabled={!canCreate || creating}>
                {creating ? 'Creating…' : 'Create Link'}
              </button>
            </div>
          </form>
        </section>

        {/* ── Links list ── */}
        <section className="sl-panel sl-panel--grow">
          <h2 className="sl-panel-title">Links</h2>
          <ul className="sl-list">
            {links.map((l) => (
              <LinkRow key={l.id} link={l} entities={entities} onRefresh={onRefresh} onError={onError} />
            ))}
            {links.length === 0 && !loading && (
              <li className="sl-empty">No links yet</li>
            )}
          </ul>
        </section>
      </div>
    </div>
  );
}
