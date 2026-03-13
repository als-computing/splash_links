import { useState, useEffect, useCallback } from 'react';
import { HubAppLayout } from '@blueskyproject/finch';
import { Database, Graph, LinkSimple } from '@phosphor-icons/react';
import * as api from './api.js';
import GraphView from './components/GraphView.jsx';
import ProjectsPage from './components/ProjectsPage.jsx';
import EntityLinker from './components/EntityLinker.jsx';

export default function App() {
  const [entities, setEntities] = useState([]);
  const [links, setLinks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const refresh = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await api.getGraph();
      setEntities(data.entities);
      setLinks(data.links);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const routes = [
    {
      path: '/',
      label: 'Projects',
      icon: <Database size={32} />,
      element: (
        <ProjectsPage
          entities={entities}
          links={links}
          loading={loading}
          error={error}
          onError={setError}
          onRefresh={refresh}
        />
      ),
    },
    {
      path: '/graph',
      label: 'Graph',
      icon: <Graph size={32} />,
      element: (
        <div style={{ width: '100%', height: '100%' }}>
          <GraphView entities={entities} links={links} />
        </div>
      ),
    },
    {
      path: '/links',
      label: 'Links',
      icon: <LinkSimple size={32} />,
      element: (
        <EntityLinker
          entities={entities}
          links={links}
          loading={loading}
          error={error}
          onError={setError}
          onRefresh={refresh}
        />
      ),
    },
  ];

  return <HubAppLayout routes={routes} headerTitle="Splash Links" />;
}
