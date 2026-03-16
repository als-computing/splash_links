import { useState } from 'react';
import * as api from '../api.js';

const PRESET_PREDICATES = ['contains', 'references', 'derived_from', 'produced', 'includes'];

export default function ProjectsPage({ entities, links, loading, error, onError, onRefresh }) {
  const [projectName, setProjectName] = useState('');
  const [creating, setCreating] = useState(false);

  const [selectedProjectId, setSelectedProjectId] = useState('');
  const [tiledUrl, setTiledUrl] = useState('');
  const [predicate, setPredicate] = useState('contains');
  const [customPredicate, setCustomPredicate] = useState('');
  const [linking, setLinking] = useState(false);

  const projects = entities.filter((e) => e.entityType === 'project');

  const handleCreateProject = async (e) => {
    e.preventDefault();
    if (!projectName.trim()) return;
    setCreating(true);
    try {
      await api.createProject(projectName.trim());
      setProjectName('');
      await onRefresh();
    } catch (err) {
      onError(err.message);
    } finally {
      setCreating(false);
    }
  };

  const handleLink = async (e) => {
    e.preventDefault();
    const url = tiledUrl.trim();
    const pred = predicate === '__custom__' ? customPredicate.trim() : predicate;
    if (!selectedProjectId || !url || !pred) return;

    setLinking(true);
    try {
      let tiledEntity = entities.find((en) => en.entityType === 'tiled' && en.uri === url);
      if (!tiledEntity) {
        const name = url.split('/').filter(Boolean).pop() || url;
        const data = await api.createEntity('tiled', name, url);
        tiledEntity = data.createEntity;
      }
      await api.createLink(selectedProjectId, pred, tiledEntity.id);
      setTiledUrl('');
      await onRefresh();
    } catch (err) {
      onError(err.message);
    } finally {
      setLinking(false);
    }
  };

  const handleDeleteLink = async (id) => {
    try {
      await api.deleteLink(id);
      await onRefresh();
    } catch (err) {
      onError(err.message);
    }
  };

  return (
    <div className="sl-page">
      {/* Error banner */}
      {error && (
        <div className="sl-error-banner" onClick={() => onError(null)}>
          {error} <span>×</span>
        </div>
      )}

      <div className="sl-panels">
        {/* ── Projects ── */}
        <section className="sl-panel">
          <h2 className="sl-panel-title">Projects</h2>
          <form onSubmit={handleCreateProject} className="sl-form-row">
            <input
              className="sl-input"
              value={projectName}
              onChange={(e) => setProjectName(e.target.value)}
              placeholder="New project name"
              disabled={creating}
            />
            <button className="sl-btn" type="submit" disabled={creating || !projectName.trim()}>
              {creating ? '…' : '+'}
            </button>
          </form>
          <ul className="sl-list">
            {projects.map((p) => (
              <li key={p.id}>
                <button
                  className={`sl-list-btn${selectedProjectId === p.id ? ' sl-list-btn--active' : ''}`}
                  onClick={() => setSelectedProjectId(p.id)}
                  title={p.id}
                >
                  <span className="sl-dot sl-dot--project" />
                  {p.name}
                </button>
              </li>
            ))}
            {projects.length === 0 && !loading && (
              <li className="sl-empty">No projects yet</li>
            )}
          </ul>
        </section>

        {/* ── Link to Tiled ── */}
        <section className="sl-panel">
          <h2 className="sl-panel-title">Link to Tiled</h2>
          <form onSubmit={handleLink} className="sl-form-col">
            <label className="sl-label">
              Project
              <select
                className="sl-input"
                value={selectedProjectId}
                onChange={(e) => setSelectedProjectId(e.target.value)}
              >
                <option value="">— select —</option>
                {projects.map((p) => (
                  <option key={p.id} value={p.id}>{p.name}</option>
                ))}
              </select>
            </label>
            <label className="sl-label">
              Tiled URL
              <input
                className="sl-input"
                value={tiledUrl}
                onChange={(e) => setTiledUrl(e.target.value)}
                placeholder="https://tiled.example.com/…"
              />
            </label>
            <label className="sl-label">
              Predicate
              <select
                className="sl-input"
                value={predicate}
                onChange={(e) => setPredicate(e.target.value)}
              >
                {PRESET_PREDICATES.map((p) => (
                  <option key={p} value={p}>{p}</option>
                ))}
                <option value="__custom__">custom…</option>
              </select>
            </label>
            {predicate === '__custom__' && (
              <input
                className="sl-input"
                value={customPredicate}
                onChange={(e) => setCustomPredicate(e.target.value)}
                placeholder="predicate name"
              />
            )}
            <button
              className="sl-btn sl-btn--full"
              type="submit"
              disabled={linking || !selectedProjectId || !tiledUrl.trim()}
            >
              {linking ? 'Linking…' : 'Create Link'}
            </button>
          </form>
        </section>

        {/* ── Links list ── */}
        <section className="sl-panel sl-panel--grow">
          <h2 className="sl-panel-title">Links</h2>
          <ul className="sl-list">
            {links.map((l) => {
              const subj = entities.find((e) => e.id === l.subjectId);
              const obj = entities.find((e) => e.id === l.objectId);
              return (
                <li key={l.id} className="sl-link-item">
                  <span className="sl-link-text">
                    <strong>{subj?.name ?? l.subjectId}</strong>
                    <em> {l.predicate} </em>
                    <strong>{obj?.name ?? l.objectId}</strong>
                  </span>
                  <button
                    className="sl-del-btn"
                    onClick={() => handleDeleteLink(l.id)}
                    title="Delete link"
                  >
                    ×
                  </button>
                </li>
              );
            })}
            {links.length === 0 && !loading && (
              <li className="sl-empty">No links yet</li>
            )}
          </ul>
        </section>
      </div>
    </div>
  );
}
