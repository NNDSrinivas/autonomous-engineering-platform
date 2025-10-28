/**
 * GraphView - Interactive graph visualization using vis-network
 */

import React, { useEffect, useRef } from 'react';
import { Network } from 'vis-network/standalone';
import type { Node, Edge } from '../hooks/useMemoryGraph';

interface GraphViewProps {
  nodes: Node[];
  edges: Edge[];
  onSelectNode?: (id: string) => void;
}

const NODE_COLORS: Record<string, string> = {
  meeting: '#9333ea',
  jira_issue: '#3b82f6',
  pr: '#10b981',
  run: '#f59e0b',
  incident: '#ef4444',
  doc: '#6366f1',
  slack_thread: '#8b5cf6',
};

export const GraphView: React.FC<GraphViewProps> = ({ nodes, edges, onSelectNode }) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const networkRef = useRef<Network | null>(null);

  useEffect(() => {
    if (!containerRef.current || nodes.length === 0) return;

    // Transform nodes for vis-network
    const visNodes = nodes.map((node) => ({
      id: node.id,
      label: truncate(node.title || node.foreign_id || `${node.id}`, 48),
      title: `${node.kind || 'node'}: ${node.foreign_id || node.id}\n${node.title || ''}`,
      color: {
        background: NODE_COLORS[node.kind || 'doc'] || '#64748b',
        border: '#334155',
        highlight: {
          background: '#fbbf24',
          border: '#f59e0b',
        },
      },
      font: { color: '#ffffff', size: 14 },
    }));

    // Transform edges for vis-network
    const visEdges = edges.map((edge) => ({
      id: edge.id,
      from: edge.src_id,
      to: edge.dst_id,
      label: edge.relation,
      arrows: 'to',
      font: { size: 11, align: 'middle' },
      color: { color: '#94a3b8', highlight: '#f59e0b' },
      smooth: { type: 'curvedCW', roundness: 0.2 },
    }));

    const data = {
      nodes: visNodes,
      edges: visEdges,
    };

    const options = {
      nodes: {
        shape: 'box',
        margin: 10,
        widthConstraint: { maximum: 200 },
      },
      edges: {
        width: 2,
        selectionWidth: 4,
      },
      physics: {
        enabled: true,
        stabilization: {
          iterations: 200,
        },
        barnesHut: {
          gravitationalConstant: -8000,
          springConstant: 0.04,
          springLength: 150,
        },
      },
      interaction: {
        hover: true,
        tooltipDelay: 200,
      },
    };

    // Create network
    const network = new Network(containerRef.current, data, options);
    networkRef.current = network;

    // Handle node selection
    network.on('click', (params) => {
      if (params.nodes.length > 0) {
        const nodeId = params.nodes[0];
        const selectedNode = nodes.find((n) => n.id === nodeId);
        if (selectedNode && onSelectNode) {
          onSelectNode(selectedNode.foreign_id || String(selectedNode.id));
        }
      }
    });

    // Cleanup
    return () => {
      network.destroy();
    };
  }, [nodes, edges, onSelectNode]);

  if (nodes.length === 0) {
    return (
      <div className="flex items-center justify-center h-full bg-gray-50 rounded-lg border-2 border-dashed border-gray-300">
        <p className="text-gray-500">No graph data available</p>
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      className="w-full h-full border border-gray-300 rounded-lg bg-white"
      style={{ minHeight: '500px' }}
    />
  );
};

function truncate(str: string, maxLen: number): string {
  if (str.length <= maxLen) return str;
  return str.slice(0, maxLen - 3) + '...';
}
