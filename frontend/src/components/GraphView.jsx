import { useRef, useEffect, useState, useMemo } from 'react';
import ForceGraph2D from 'react-force-graph-2d';

const NODE_COLOR = {
  project: '#0ea5e9', // sky-500 – matches Finch active/accent
  tiled: '#f97316',   // orange-500
};

const NODE_RADIUS = 7;

function paintNode(node, ctx, globalScale) {
  const color = NODE_COLOR[node.type] ?? '#6b7280';

  // Circle
  ctx.beginPath();
  ctx.arc(node.x, node.y, NODE_RADIUS, 0, 2 * Math.PI);
  ctx.fillStyle = color;
  ctx.fill();
  ctx.strokeStyle = 'rgba(255,255,255,0.85)';
  ctx.lineWidth = 1.5 / globalScale;
  ctx.stroke();

  // Label — constant screen size
  const fontSize = 12 / globalScale;
  ctx.font = `500 ${fontSize}px Inter, system-ui, sans-serif`;
  ctx.fillStyle = '#1f2937';
  ctx.textAlign = 'center';
  ctx.fillText(node.name, node.x, node.y + NODE_RADIUS + fontSize + 1 / globalScale);
}

export default function GraphView({ entities, links }) {
  const containerRef = useRef(null);
  const fgRef = useRef(null);
  const [dims, setDims] = useState({ width: 100, height: 100 });

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const obs = new ResizeObserver(([entry]) => {
      const { width, height } = entry.contentRect;
      setDims({ width, height });
    });
    obs.observe(el);
    return () => obs.disconnect();
  }, []);

  useEffect(() => {
    const fg = fgRef.current;
    if (!fg) return;
    fg.d3Force('link').distance(200);
    fg.d3Force('charge').strength(-400);
  }, []);

  // Build graph data; create fresh objects so react-force-graph can mutate freely
  const graphData = useMemo(
    () => ({
      nodes: entities.map((e) => ({
        id: e.id,
        name: e.name,
        type: e.entityType,
        uri: e.uri,
      })),
      links: links.map((l) => ({
        id: l.id,
        source: l.subjectId,
        target: l.objectId,
        predicate: l.predicate,
      })),
    }),
    [entities, links],
  );

  const isEmpty = entities.length === 0;

  return (
    <div ref={containerRef} style={{ width: '100%', height: '100%', position: 'relative' }}>
      {/* Legend */}
      <div
        style={{
          position: 'absolute',
          top: 10,
          right: 14,
          display: 'flex',
          gap: 14,
          fontSize: 12,
          color: '#6b7280',
          zIndex: 10,
          background: 'rgba(255,255,255,0.85)',
          padding: '5px 10px',
          borderRadius: 8,
          border: '1px solid #e5e7eb',
        }}
      >
        {Object.entries(NODE_COLOR).map(([type, color]) => (
          <span key={type} style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
            <span
              style={{
                display: 'inline-block',
                width: 10,
                height: 10,
                borderRadius: '50%',
                background: color,
              }}
            />
            {type}
          </span>
        ))}
      </div>

      <ForceGraph2D
        ref={fgRef}
        width={dims.width}
        height={dims.height}
        graphData={graphData}
        onEngineStop={() => {}}
        d3VelocityDecay={0.3}
        d3AlphaDecay={0.02}
        nodeId="id"

        nodeCanvasObject={paintNode}
        nodeCanvasObjectMode={() => 'replace'}
        nodeLabel={(node) =>
          `${node.type}: ${node.name}${node.uri ? '\n' + node.uri : ''}`
        }
        linkLabel="predicate"
        linkColor={() => '#9ca3af'}
        linkWidth={1.5}
        linkDirectionalArrowLength={6}
        linkDirectionalArrowRelPos={1}
        linkDirectionalArrowColor={() => '#6b7280'}
        linkCanvasObjectMode={() => 'after'}
        linkCanvasObject={(link, ctx, globalScale) => {
          if (!link.predicate) return;
          const start = link.source;
          const end = link.target;
          if (typeof start !== 'object' || typeof end !== 'object') return;
          const midX = (start.x + end.x) / 2;
          const midY = (start.y + end.y) / 2;
          const fontSize = Math.max(10 / globalScale, 2);
          ctx.font = `${fontSize}px Inter, system-ui, sans-serif`;
          const label = link.predicate;
          const textWidth = ctx.measureText(label).width;
          const padding = 2 / globalScale;
          ctx.fillStyle = 'rgba(255,255,255,0.85)';
          ctx.fillRect(midX - textWidth / 2 - padding, midY - fontSize / 2 - padding, textWidth + padding * 2, fontSize + padding * 2);
          ctx.fillStyle = '#374151';
          ctx.textAlign = 'center';
          ctx.textBaseline = 'middle';
          ctx.fillText(label, midX, midY);
        }}
        backgroundColor="#f8f9fa"
        cooldownTicks={120}
      />

      {isEmpty && (
        <div
          style={{
            position: 'absolute',
            inset: 0,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 8,
            color: '#9ca3af',
            fontSize: 14,
            pointerEvents: 'none',
          }}
        >
          <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#d1d5db" strokeWidth="1.5">
            <circle cx="12" cy="12" r="4" />
            <circle cx="4" cy="6" r="2" />
            <circle cx="20" cy="6" r="2" />
            <circle cx="20" cy="18" r="2" />
            <line x1="6" y1="7" x2="10" y2="10" />
            <line x1="18" y1="7" x2="14" y2="10" />
            <line x1="18" y1="17" x2="14" y2="14" />
          </svg>
          Create a project, then link it to a Tiled URL
        </div>
      )}
    </div>
  );
}
