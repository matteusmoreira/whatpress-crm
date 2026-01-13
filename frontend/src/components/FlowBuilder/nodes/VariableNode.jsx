import React, { memo } from 'react';
import { Handle, Position } from '@xyflow/react';

const VariableNode = ({ data, selected }) => {
    const action = data.config?.action || 'set';
    const variableName = data.config?.variableName || '';

    return (
        <div className={`custom-node variable-node ${selected ? 'selected' : ''}`}>
            <div className="node-header">
                <span className="node-icon">📝</span>
                <span className="node-title">{data.label || 'Variável'}</span>
            </div>
            <div className="node-body">
                <div className="node-description">
                    {action === 'set' ? 'Definir' : 'Obter'} {variableName || 'variável'}
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
                className="custom-handle"
            />
        </div>
    );
};

export default memo(VariableNode);
