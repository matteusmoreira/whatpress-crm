import React from 'react';
import { NODE_TYPES, NODE_DESCRIPTIONS, NODE_CATEGORIES, createNode } from '../../../lib/flowTypes';
import useFlowStore from '../../../store/flowStore';

const NodeToolbar = () => {
    const { addNode } = useFlowStore();

    const handleDragStart = (event, nodeType) => {
        event.dataTransfer.setData('application/reactflow-node-type', nodeType);
        event.dataTransfer.effectAllowed = 'move';
    };

    const handleClick = (nodeType) => {
        // Adiciona o nó no centro da tela
        const newNode = createNode(nodeType, { x: 250, y: 250 });
        addNode(newNode);
    };

    // Agrupar nós por categoria
    const nodesByCategory = Object.entries(NODE_TYPES).reduce((acc, [key, type]) => {
        const desc = NODE_DESCRIPTIONS[type];
        if (!desc) return acc;

        const category = desc.category;
        if (!acc[category]) {
            acc[category] = [];
        }

        acc[category].push({
            type,
            ...desc
        });

        return acc;
    }, {});

    // Ordenar categorias
    const sortedCategories = Object.entries(nodesByCategory).sort((a, b) => {
        const orderA = NODE_CATEGORIES[a[0]]?.order || 999;
        const orderB = NODE_CATEGORIES[b[0]]?.order || 999;
        return orderA - orderB;
    });

    return (
        <div className="node-toolbar">
            <div className="panel-header">
                <h3>Componentes</h3>
            </div>

            <div className="node-categories">
                {sortedCategories.map(([categoryKey, nodes]) => (
                    <div key={categoryKey} className="node-category">
                        <h4 className="category-title">
                            {NODE_CATEGORIES[categoryKey]?.label || categoryKey}
                        </h4>

                        <div className="node-items">
                            {nodes.map((node) => (
                                <div
                                    key={node.type}
                                    className="node-item"
                                    draggable
                                    onDragStart={(e) => handleDragStart(e, node.type)}
                                    onClick={() => handleClick(node.type)}
                                    title={node.description}
                                >
                                    <span className="node-item-icon">{node.icon}</span>
                                    <div className="node-item-content">
                                        <span className="node-item-title">{node.title}</span>
                                        <span className="node-item-description">{node.description}</span>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                ))}
            </div>

            <div className="toolbar-footer">
                <p className="text-xs text-muted-foreground">
                    Arraste os componentes para o canvas ou clique para adicionar
                </p>
            </div>
        </div>
    );
};

export default NodeToolbar;
