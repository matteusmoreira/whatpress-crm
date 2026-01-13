import React, { memo } from 'react';
import { Handle, Position } from '@xyflow/react';

const ConditionalNode = ({ data, selected }) => {
    const condition = data.config?.condition || {};

    return (
        <div className={`custom-node conditional-node ${selected ? 'selected' : ''}`}>
            <div className="node-header">
                <span className="node-icon">🔀</span>
                <span className="node-title">{data.label || 'Condicional'}</span>
            </div>
            <div className="node-body">
                <div className="node-description">
                    {condition.variable ? `Se ${condition.variable}` : 'Configure a condição'}
                </div>
            </div>
            <Handle
                type="target"
                position={Position.Top}
                className="custom-handle"
            />
            <Handle
                type="source"
                position={Position.Bottom}
                id="true"
                className="custom-handle handle-true"
                style={{ left: '30%' }}
            />
            <Handle
                type="source"
                position={Position.Bottom}
                id="false"
                className="custom-handle handle-false"
                style={{ left: '70%' }}
            />
        </div>
    );
};

export default memo(ConditionalNode);
